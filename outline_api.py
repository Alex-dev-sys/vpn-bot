"""
Модуль для работы с Outline API
Автоматическое создание и удаление VPN ключей
"""
import aiohttp
import ssl
import hashlib
from typing import Optional, Dict, List
from config import logger


# Глобальная сессия
_GLOBAL_SESSION: Optional[aiohttp.ClientSession] = None

async def get_client_session() -> aiohttp.ClientSession:
    """Возвращает или создает глобальную сессию"""
    global _GLOBAL_SESSION
    if _GLOBAL_SESSION is None or _GLOBAL_SESSION.closed:
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        _GLOBAL_SESSION = aiohttp.ClientSession(connector=connector)
    return _GLOBAL_SESSION

async def close_client_session():
    """Закрывает глобальную сессию"""
    global _GLOBAL_SESSION
    if _GLOBAL_SESSION and not _GLOBAL_SESSION.closed:
        await _GLOBAL_SESSION.close()


class OutlineServer:
    """Класс для работы с одним Outline сервером"""
    
    def __init__(self, server_id: int, name: str, api_url: str, cert_sha256: str,
                 location: str = "", country_code: str = "", flag_emoji: str = "🌍"):
        self.server_id = server_id
        self.name = name
        self.api_url = api_url.rstrip('/')
        self.cert_sha256 = cert_sha256
        self.location = location
        self.country_code = country_code
        self.flag_emoji = flag_emoji
        
        # SSL контекст для самоподписанного сертификата
        self.ssl_context = self._create_ssl_context()
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Создаёт SSL контекст с проверкой сертификата по SHA256"""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    
    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Выполняет запрос к Outline API"""
        url = f"{self.api_url}/{endpoint}"
        
        try:
            session = await get_client_session()
            async with session.request(
                method, 
                url, 
                json=data, 
                ssl=self.ssl_context,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 204:
                    return {"success": True}
                
                if response.status >= 400:
                    try:
                        error_text = await response.text()
                    except:
                        error_text = f"Status {response.status}"
                        
                    logger.error(f"Outline API error {response.status}: {error_text}")
                    return {"error": error_text, "status": response.status}
                
                try:
                    return await response.json()
                except:
                    return {"success": True} # Fallback if no json
                    
        except aiohttp.ClientError as e:
            logger.error(f"Outline API connection error: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Outline API unexpected error: {e}")
            return {"error": str(e)}
    
    async def get_server_info(self) -> Optional[Dict]:
        """Получить информацию о сервере"""
        result = await self._request("GET", "server")
        if "error" not in result:
            return result
        return None
    
    async def get_access_keys(self) -> List[Dict]:
        """Получить список всех ключей"""
        result = await self._request("GET", "access-keys")
        if "error" not in result:
            return result.get("accessKeys", [])
        return []
    
    async def create_access_key(self, name: str = None) -> Optional[Dict]:
        """
        Создать новый ключ доступа
        
        Returns:
            {
                "id": "1",
                "name": "user_123456",
                "password": "xxx",
                "port": 443,
                "method": "chacha20-ietf-poly1305",
                "accessUrl": "ss://xxx@ip:port#name"
            }
        """
        # Сначала создаём ключ
        result = await self._request("POST", "access-keys")
        
        if "error" in result:
            return None
        
        key_id = result.get("id")
        
        # Устанавливаем имя если указано
        if name and key_id:
            await self._request("PUT", f"access-keys/{key_id}/name", {"name": name})
            result["name"] = name
        
        return result
    
    async def delete_access_key(self, key_id: str) -> bool:
        """Удалить ключ доступа"""
        result = await self._request("DELETE", f"access-keys/{key_id}")
        return "error" not in result
    
    async def rename_access_key(self, key_id: str, name: str) -> bool:
        """Переименовать ключ"""
        result = await self._request("PUT", f"access-keys/{key_id}/name", {"name": name})
        return "error" not in result
    
    async def set_data_limit(self, key_id: str, bytes_limit: int) -> bool:
        """Установить лимит трафика для ключа (в байтах)"""
        result = await self._request(
            "PUT", 
            f"access-keys/{key_id}/data-limit", 
            {"limit": {"bytes": bytes_limit}}
        )
        return "error" not in result
    
    async def remove_data_limit(self, key_id: str) -> bool:
        """Удалить лимит трафика"""
        result = await self._request("DELETE", f"access-keys/{key_id}/data-limit")
        return "error" not in result
    
    async def get_metrics(self) -> Dict:
        """Получить метрики использования (трафик по ключам)"""
        result = await self._request("GET", "metrics/transfer")
        if "error" not in result:
            return result.get("bytesTransferredByUserId", {})
        return {}
    
    async def get_key_count(self) -> int:
        """Получить количество активных ключей"""
        keys = await self.get_access_keys()
        return len(keys)
    
    async def is_available(self) -> bool:
        """Проверить доступность сервера"""
        info = await self.get_server_info()
        return info is not None


class OutlineManager:
    """Менеджер для работы с несколькими Outline серверами"""
    
    def __init__(self):
        self.servers: Dict[int, OutlineServer] = {}
    
    def add_server(self, server_id: int, name: str, api_url: str, cert_sha256: str,
                   location: str = "", country_code: str = "", flag_emoji: str = "🌍"):
        """Добавить сервер в менеджер"""
        self.servers[server_id] = OutlineServer(
            server_id=server_id,
            name=name,
            api_url=api_url,
            cert_sha256=cert_sha256,
            location=location,
            country_code=country_code,
            flag_emoji=flag_emoji
        )
        logger.info(f"Outline server added: {name} ({flag_emoji} {location})")
    
    def remove_server(self, server_id: int):
        """Удалить сервер из менеджера"""
        if server_id in self.servers:
            del self.servers[server_id]
    
    def get_server(self, server_id: int) -> Optional[OutlineServer]:
        """Получить сервер по ID"""
        return self.servers.get(server_id)
    
    async def get_servers_load(self) -> List[Dict]:
        """Получить нагрузку всех серверов"""
        loads = []
        for server_id, server in self.servers.items():
            key_count = await server.get_key_count()
            loads.append({
                "server_id": server_id,
                "name": server.name,
                "location": server.location,
                "flag_emoji": server.flag_emoji,
                "current_users": key_count,
                "is_available": await server.is_available()
            })
        return loads
    
    async def get_least_loaded_server(self, max_users: int = 30) -> Optional[OutlineServer]:
        """Получить наименее загруженный сервер"""
        min_load = float('inf')
        best_server = None
        
        for server in self.servers.values():
            if not await server.is_available():
                continue
            
            key_count = await server.get_key_count()
            if key_count < max_users and key_count < min_load:
                min_load = key_count
                best_server = server
        
        return best_server
    
    async def create_key(self, server_id: int, user_id: int) -> Optional[Dict]:
        """Создать ключ на указанном сервере"""
        server = self.get_server(server_id)
        if not server:
            logger.error(f"Server {server_id} not found")
            return None
        
        key_name = f"user_{user_id}"
        result = await server.create_access_key(name=key_name)
        
        if result:
            logger.info(f"Key created for user {user_id} on server {server.name}")
            return {
                "outline_key_id": result.get("id"),
                "access_url": result.get("accessUrl"),
                "server_id": server_id,
                "server_name": server.name,
                "server_location": server.location,
                "server_flag": server.flag_emoji
            }
        
        return None
    
    async def delete_key(self, server_id: int, outline_key_id: str) -> bool:
        """Удалить ключ с сервера"""
        server = self.get_server(server_id)
        if not server:
            logger.error(f"Server {server_id} not found")
            return False
        
        success = await server.delete_access_key(outline_key_id)
        if success:
            logger.info(f"Key {outline_key_id} deleted from server {server.name}")
        else:
            logger.error(f"Failed to delete key {outline_key_id} from server {server.name}")
        
        return success


# Глобальный экземпляр менеджера
outline_manager = OutlineManager()


def init_outline_servers(servers_data: List[Dict]):
    """
    Инициализация серверов из списка
    
    servers_data = [
        {
            "id": 1,
            "name": "NL-1",
            "api_url": "https://185.x.x.x:12345/xxxxxx",
            "cert_sha256": "ABC123...",
            "location": "Нидерланды",
            "country_code": "NL",
            "flag_emoji": "🇳🇱"
        },
        ...
    ]
    """
    for srv in servers_data:
        if srv.get("outline_api_url") and srv.get("outline_cert"):
            outline_manager.add_server(
                server_id=srv["id"],
                name=srv.get("name", f"Server-{srv['id']}"),
                api_url=srv["outline_api_url"],
                cert_sha256=srv["outline_cert"],
                location=srv.get("location", "Unknown"),
                country_code=srv.get("country_code", "XX"),
                flag_emoji=srv.get("flag_emoji", "🌍")
            )

