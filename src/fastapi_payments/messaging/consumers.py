from typing import Dict, Any, Optional, Callable, Awaitable, List
import importlib
import logging
import asyncio

logger = logging.getLogger(__name__)


# Simple in-memory router for testing
class InMemoryRouter:
    def __init__(self):
        self.subscribers = {}

    def subscriber(self, routing_key=None, **kwargs):
        def decorator(func):
            if routing_key not in self.subscribers:
                self.subscribers[routing_key] = []
            self.subscribers[routing_key].append(func)
            return func

        return decorator


class PaymentEventConsumer:
    """Consumer for payment-related events."""

    def __init__(self, config):
        """
        Initialize the payment event consumer.

        Args:
            config: Message broker configuration
        """
        self.config = config
        self.broker, self.router = self._initialize_broker()

        # Event handlers
        self.handlers = {}
        self.subscribers = []

    def _initialize_broker(self):
        """
        Initialize the message broker based on configuration.

        Returns:
            Tuple of (broker, router)
        """
        broker_type = getattr(self.config, "broker_type",
                              "redis")  # Default to Redis

        # Try Redis broker first (our default)
        if broker_type == "redis" or broker_type == "memory":
            try:
                # Dynamically import Redis broker
                redis_module = importlib.import_module("faststream.redis")
                RedisBroker = redis_module.RedisBroker
                RedisRouter = redis_module.RedisRouter

                broker = RedisBroker(
                    getattr(self.config, "url", "redis://localhost:6379")
                )
                router = RedisRouter()
                self.stream_maxlen = getattr(
                    self.config, "stream_maxlen", 1000)
                self.consumer_group = getattr(
                    self.config, "consumer_group", "payment-service"
                )
                logger.info(
                    f"Initialized Redis broker at {
                        getattr(self.config, 'url', 'redis://localhost:6379')}"
                )
                return broker, router
            except ImportError:
                logger.warning(
                    "Redis broker not available. "
                    "Install with 'pip install \"fastapi-payments[redis]\"'. "
                    "Falling back to in-memory broker."
                )
                from ..messaging.publishers import InMemoryBroker

                return InMemoryBroker(), InMemoryRouter()

        # Try RabbitMQ broker
        elif broker_type == "rabbitmq":
            try:
                # Dynamically import RabbitMQ broker
                rabbit_module = importlib.import_module("faststream.rabbit")
                RabbitBroker = rabbit_module.RabbitBroker
                RabbitRouter = rabbit_module.RabbitRouter

                broker = RabbitBroker(self.config.url)
                router = RabbitRouter()
                self.exchange_name = getattr(
                    self.config, "exchange_name", "payments")
                self.exchange_settings = {
                    "exchange_type": getattr(self.config, "exchange_type", "topic"),
                    "durable": getattr(self.config, "exchange_durable", True),
                }
                logger.info(f"Initialized RabbitMQ broker at {
                            self.config.url}")
                return broker, router
            except ImportError:
                logger.warning(
                    "RabbitMQ broker requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[rabbitmq]\"'. "
                    "Falling back to in-memory broker."
                )
                from ..messaging.publishers import InMemoryBroker

                return InMemoryBroker(), InMemoryRouter()

        # Try Kafka broker
        elif broker_type == "kafka":
            try:
                # Dynamically import Kafka broker
                kafka_module = importlib.import_module("faststream.kafka")
                KafkaBroker = kafka_module.KafkaBroker
                KafkaRouter = kafka_module.KafkaRouter

                broker = KafkaBroker(self.config.url)
                router = KafkaRouter()
                self.topic_prefix = getattr(
                    self.config, "topic_prefix", "payments.")
                self.group_id = getattr(
                    self.config, "group_id", "payment-service")
                self.auto_offset_reset = getattr(
                    self.config, "auto_offset_reset", "earliest"
                )
                logger.info(f"Initialized Kafka broker at {self.config.url}")
                return broker, router
            except ImportError:
                logger.warning(
                    "Kafka broker requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[kafka]\"'. "
                    "Falling back to in-memory broker."
                )
                from ..messaging.publishers import InMemoryBroker

                return InMemoryBroker(), InMemoryRouter()

        # Try NATS broker
        elif broker_type == "nats":
            try:
                # Dynamically import NATS broker
                nats_module = importlib.import_module("faststream.nats")
                NatsBroker = nats_module.NatsBroker
                NatsRouter = nats_module.NatsRouter

                broker = NatsBroker(self.config.url)
                router = NatsRouter()
                self.subject_prefix = getattr(
                    self.config, "subject_prefix", "payments."
                )
                self.queue_group = getattr(
                    self.config, "queue_group", "payment-service"
                )
                logger.info(f"Initialized NATS broker at {self.config.url}")
                return broker, router
            except ImportError:
                logger.warning(
                    "NATS broker requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[nats]\"'. "
                    "Falling back to in-memory broker."
                )
                from ..messaging.publishers import InMemoryBroker

                return InMemoryBroker(), InMemoryRouter()

        # Fallback to in-memory broker
        else:
            logger.warning(
                f"Unsupported broker type: {
                    broker_type}. Falling back to in-memory broker."
            )
            from ..messaging.publishers import InMemoryBroker

            return InMemoryBroker(), InMemoryRouter()

    async def register_handler(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """
        Register a handler for a specific event type.

        Args:
            event_type: Type of event (e.g., payment.created)
            handler: Async handler function
        """
        self.handlers[event_type] = handler

        # Create queue and binding for this event type
        broker_type = getattr(self.config, "broker_type", "redis")
        queue_name = f"{getattr(self.config, 'queue_prefix', 'payment_')}{
            event_type.replace('.', '_')}"

        try:
            if broker_type == "rabbitmq":
                # Only try to use RabbitMQ-specific features if we have a RabbitMQ router
                from faststream.rabbit import RabbitRouter

                if isinstance(self.router, RabbitRouter):
                    subscriber = self.router.subscriber(
                        self.exchange_name,
                        routing_key=event_type,
                        queue_name=queue_name,
                        **self.exchange_settings,
                    )

                    @subscriber
                    async def event_handler(message: Dict[str, Any]):
                        await self._process_message(event_type, message)

                    self.subscribers.append(event_handler)
                else:
                    await self._register_memory_handler(event_type)

            elif broker_type == "kafka":
                from faststream.kafka import KafkaRouter

                if isinstance(self.router, KafkaRouter):
                    topic = f"{self.topic_prefix}{
                        event_type.replace('.', '_')}"

                    @self.router.subscriber(
                        topic,
                        group_id=self.group_id,
                        auto_offset_reset=self.auto_offset_reset,
                    )
                    async def event_handler(message: Dict[str, Any]):
                        await self._process_message(event_type, message)

                    self.subscribers.append(event_handler)
                else:
                    await self._register_memory_handler(event_type)

            elif broker_type == "redis":
                from faststream.redis import RedisRouter

                if isinstance(self.router, RedisRouter):
                    stream = f"{getattr(self.config, 'exchange_name', 'payments')}:{
                        event_type.replace('.', ':')}"

                    @self.router.subscriber(stream, consumer_group=self.consumer_group)
                    async def event_handler(message: Dict[str, Any]):
                        await self._process_message(event_type, message)

                    self.subscribers.append(event_handler)
                else:
                    await self._register_memory_handler(event_type)

            elif broker_type == "nats":
                from faststream.nats import NatsRouter

                if isinstance(self.router, NatsRouter):
                    subject = f"{self.subject_prefix}{
                        event_type.replace('.', '.')}"

                    @self.router.subscriber(subject, queue=self.queue_group)
                    async def event_handler(message: Dict[str, Any]):
                        await self._process_message(event_type, message)

                    self.subscribers.append(event_handler)
                else:
                    await self._register_memory_handler(event_type)

            else:  # Fallback to memory broker
                await self._register_memory_handler(event_type)

            logger.info(f"Registered handler for event type: {event_type}")

        except ImportError:
            # If any imports fail, fall back to memory broker
            await self._register_memory_handler(event_type)

    async def _register_memory_handler(self, event_type: str):
        """Register handler with memory broker as fallback."""
        if isinstance(self.router, InMemoryRouter):

            @self.router.subscriber(routing_key=event_type)
            async def event_handler(message: Dict[str, Any]):
                await self._process_message(event_type, message)

            self.subscribers.append(event_handler)
        else:
            # Just save the handler to be called manually
            logger.warning(
                f"Using basic handler registration for {event_type}")

    async def _process_message(self, event_type: str, message: Dict[str, Any]):
        """
        Process an incoming message.

        Args:
            event_type: Type of event
            message: Event message
        """
        try:
            logger.info(f"Received {event_type} event")

            # Call the registered handler
            handler = self.handlers.get(event_type)
            if handler:
                await handler(message)
            else:
                logger.warning(
                    f"No handler registered for event type: {event_type}")
        except Exception as e:
            logger.error(f"Error processing {event_type} event: {str(e)}")
            # Consider implementing retry logic or dead-letter queue

    async def start(self):
        """Start consuming messages."""
        # Include router in broker
        self.broker.include_router(self.router)

        # Start the broker
        await self.broker.start()

        logger.info(
            f"Payment event consumer started with {
                len(self.handlers)} handlers"
        )

    async def stop(self):
        """Stop consuming messages."""
        await self.broker.close()
        logger.info("Payment event consumer stopped")


# Example predefined event handlers
class DefaultHandlers:
    """Default handlers for common payment events."""

    @staticmethod
    async def handle_payment_succeeded(message: Dict[str, Any]):
        """Handle payment.succeeded events."""
        logger.info(
            f"Processing successful payment: {
                message.get('data', {}).get('payment_id')}"
        )
        # Implement business logic for successful payments

    @staticmethod
    async def handle_payment_failed(message: Dict[str, Any]):
        """Handle payment.failed events."""
        logger.info(
            f"Processing failed payment: {
                message.get('data', {}).get('payment_id')}"
        )
        # Implement business logic for failed payments

    @staticmethod
    async def handle_subscription_canceled(message: Dict[str, Any]):
        """Handle subscription.canceled events."""
        logger.info(
            f"Processing canceled subscription: {
                message.get('data', {}).get('subscription_id')}"
        )
        # Implement business logic for canceled subscriptions


async def setup_default_consumers(consumer: PaymentEventConsumer):
    """
    Set up default consumers with standard handlers.

    Args:
        consumer: PaymentEventConsumer instance
    """
    handlers = DefaultHandlers()

    # Register default handlers
    await consumer.register_handler(
        "payment.transaction.succeeded", handlers.handle_payment_succeeded
    )
    await consumer.register_handler(
        "payment.transaction.failed", handlers.handle_payment_failed
    )
    await consumer.register_handler(
        "payment.subscription.canceled", handlers.handle_subscription_canceled
    )
