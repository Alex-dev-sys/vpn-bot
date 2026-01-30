"""
Модуль для работы с YooMoney (ЮMoney)
Автоматическая генерация ссылок и проверка оплаты
"""
import uuid
from yoomoney import Client, Quickpay
from config import YOOMONEY_TOKEN, YOOMONEY_WALLET, logger

class YooMoneyManager:
    def __init__(self):
        self.token = YOOMONEY_TOKEN
        self.wallet = YOOMONEY_WALLET
        self.client = None
        
        if self.token:
            try:
                self.client = Client(self.token)
                user = self.client.account_info()
                logger.info(f"YooMoney authorized: Account {user.account}")
            except Exception as e:
                logger.error(f"YooMoney auth error: {e}")

    def create_payment_link(self, amount: int, label: str, description: str) -> str:
        """
        Создать ссылку на оплату
        :param amount: Сумма в рублях
        :param label: Уникальная метка заказа (например, id подписки)
        :param description: Описание платежа
        :return: Ссылка на оплату
        """
        if not self.wallet:
            return ""

        try:
            quickpay = Quickpay(
                receiver=self.wallet,
                quickpay_form="shop",
                targets=description,
                paymentType="SB",  # Сбербанк Онлайн, банковская карта и т.д.
                sum=amount,
                label=label
            )
            return quickpay.base_url
        except Exception as e:
            logger.error(f"Error creating payment link: {e}")
            return ""

    def check_payment(self, label: str, expected_amount: int = 0) -> bool:
        """
        Проверить наличие успешного платежа с указанной меткой и суммой
        :param label: Метка заказа (id подписки)
        :param expected_amount: Ожидаемая сумма платежа
        :return: True если оплачено корректно
        """
        if not self.client:
            return False

        try:
            history = self.client.operation_history(label=label)
            for operation in history.operations:
                if operation.status == 'success':
                    # Проверяем сумму
                    if expected_amount > 0 and operation.amount < expected_amount:
                        logger.warning(f"Payment {label}: amount {operation.amount} < expected {expected_amount}")
                        continue
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking payment history: {e}")
            return False

# Глобальный экземпляр
payment_manager = YooMoneyManager()
