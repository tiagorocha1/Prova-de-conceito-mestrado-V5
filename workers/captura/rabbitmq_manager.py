import asyncio
import json
import aio_pika
from datetime import datetime

class RabbitMQManager:
    """ Gerencia a conexão com RabbitMQ, garantindo que não seja fechada prematuramente. """

    def __init__(self):
        self.connection = None
        self.channel = None
        self.loop = asyncio.get_event_loop()

    async def connect(self):
        """ Mantém uma conexão aberta e persistente com o RabbitMQ """
        if self.connection is None or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
            self.channel = await self.connection.channel()
            await self.channel.declare_exchange("direct_exchange", aio_pika.ExchangeType.DIRECT, durable=True)
            await self.channel.declare_queue("frame", durable=True)
            print("✅ Conectado ao RabbitMQ e canal configurado!")

    async def send_message(self, minio_path: str):
        """ Envia a mensagem garantindo que a conexão esteja ativa """
        await self.connect()

        try:
            timestamp = datetime.now()
            message_body = json.dumps({"minio_path": minio_path,
                                       "data_captura_frame": timestamp.strftime("%Y-%m-%d"),
                                       "hora_captura_frame": timestamp.strftime("%H:%M:%S.%f")})
            message = aio_pika.Message(
                body=message_body.encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )

            await self.channel.default_exchange.publish(message, routing_key="frame")
            print(f"✅ Mensagem enviada com sucesso: {message_body}")

        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")

rabbitmq_manager = RabbitMQManager()
