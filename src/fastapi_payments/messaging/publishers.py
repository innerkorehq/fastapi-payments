import json
from enum import Enum
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime, timezone
import logging
import importlib
import asyncio

logger = logging.getLogger(__name__)


class PaymentEvents(str, Enum):
    """Standard payment event types."""

    CUSTOMER_CREATED = "payment.customer.created"
    CUSTOMER_UPDATED = "payment.customer.updated"
    PAYMENT_METHOD_CREATED = "payment.method.created"
    PAYMENT_METHOD_DELETED = "payment.method.deleted"
    PRODUCT_CREATED = "payment.product.created"
    PLAN_CREATED = "payment.plan.created"
    SUBSCRIPTION_CREATED = "payment.subscription.created"
    SUBSCRIPTION_UPDATED = "payment.subscription.updated"
    SUBSCRIPTION_CANCELED = "payment.subscription.canceled"
    PAYMENT_CREATED = "payment.transaction.created"
    PAYMENT_SUCCEEDED = "payment.transaction.succeeded"
    PAYMENT_FAILED = "payment.transaction.failed"
    PAYMENT_REFUNDED = "payment.transaction.refunded"
    USAGE_RECORDED = "payment.usage.recorded"
    INVOICE_CREATED = "payment.invoice.created"
    INVOICE_PAID = "payment.invoice.paid"


# Simple in-memory broker implementation for testing purposes
class InMemoryBroker:
    """Simple in-memory message broker for testing."""

    def __init__(self):
        """Initialize the in-memory broker."""
        self.messages = []
        self.subscribers = {}
        logger.info("Initialized in-memory broker")

    async def publish(self, message: Any, **kwargs) -> None:
        """Publish a message to the in-memory broker."""
        routing_key = kwargs.get("routing_key", "default")
        self.messages.append(
            {
                "message": message,
                "routing_key": routing_key,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "options": kwargs,
            }
        )
        logger.debug(
            f"Published message to in-memory broker with routing key {routing_key}"
        )

        # Notify subscribers if any
        if routing_key in self.subscribers:
            for callback in self.subscribers[routing_key]:
                try:
                    asyncio.create_task(callback(message))
                except Exception as e:
                    logger.error(
                        f"Error calling subscriber callback: {str(e)}")

    async def subscribe(self, routing_key: str, callback: Callable) -> None:
        """Subscribe to messages with a specific routing key."""
        if routing_key not in self.subscribers:
            self.subscribers[routing_key] = []
        self.subscribers[routing_key].append(callback)

    async def start(self) -> None:
        """Start the broker."""
        logger.info("Started in-memory broker")

    async def close(self) -> None:
        """Close the broker."""
        self.messages.clear()
        self.subscribers.clear()
        logger.info("Stopped in-memory broker")


class PaymentEventPublisher:
    """Publisher for payment-related events."""

    def __init__(self, config):
        """
        Initialize the payment event publisher.

        Args:
            config: Message broker configuration
        """
        self.config = config
        self.broker = self._initialize_broker()

    def _initialize_broker(self):
        """
        Initialize the message broker based on configuration.

        Returns:
            Initialized broker instance
        """
        broker_type = getattr(self.config, "broker_type",
                              "redis")  # Default to Redis

        # Try Redis broker first (our default)
        if broker_type == "redis" or broker_type == "memory":
            try:
                broker_module = importlib.import_module("faststream.redis")
                RedisBroker = broker_module.RedisBroker

                redis_url = getattr(self.config, "url",
                                    "redis://localhost:6379")
                broker = RedisBroker(redis_url)
                self.stream_maxlen = getattr(
                    self.config, "stream_maxlen", 1000)
                logger.info(f"Initialized Redis broker at {redis_url}")
                return broker
            except ImportError:
                logger.warning(
                    "Redis broker not available. "
                    "Install with 'pip install \"fastapi-payments[redis]\"'. "
                    "Falling back to in-memory broker."
                )
                return InMemoryBroker()

        # Try RabbitMQ broker
        elif broker_type == "rabbitmq":
            try:
                broker_module = importlib.import_module("faststream.rabbit")
                RabbitBroker = broker_module.RabbitBroker

                broker = RabbitBroker(self.config.url)
                self.exchange_name = getattr(
                    self.config, "exchange_name", "payments")
                self.exchange_settings = {
                    "exchange_type": getattr(self.config, "exchange_type", "topic"),
                    "durable": getattr(self.config, "exchange_durable", True),
                }
                logger.info(f"Initialized RabbitMQ broker at {self.config.url}")
                return broker
            except ImportError:
                logger.warning(
                    "RabbitMQ broker requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[rabbitmq]\"'. "
                    "Falling back to in-memory broker."
                )
                return InMemoryBroker()

        # Try Kafka broker
        elif broker_type == "kafka":
            try:
                broker_module = importlib.import_module("faststream.kafka")
                KafkaBroker = broker_module.KafkaBroker

                broker = KafkaBroker(self.config.url)
                self.topic_prefix = getattr(
                    self.config, "topic_prefix", "payments.")
                logger.info(f"Initialized Kafka broker at {self.config.url}")
                return broker
            except ImportError:
                logger.warning(
                    "Kafka broker requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[kafka]\"'. "
                    "Falling back to in-memory broker."
                )
                return InMemoryBroker()

        # Try NATS broker
        elif broker_type == "nats":
            try:
                broker_module = importlib.import_module("faststream.nats")
                NatsBroker = broker_module.NatsBroker

                broker = NatsBroker(self.config.url)
                self.subject_prefix = getattr(
                    self.config, "subject_prefix", "payments."
                )
                logger.info(f"Initialized NATS broker at {self.config.url}")
                return broker
            except ImportError:
                logger.warning(
                    "NATS broker requested but dependencies not available. "
                    "Install with 'pip install \"fastapi-payments[nats]\"'. "
                    "Falling back to in-memory broker."
                )
                return InMemoryBroker()

        # Fallback to in-memory broker
        else:
            logger.warning(
                f"Unsupported broker type: {broker_type}. Falling back to in-memory broker."
            )
            return InMemoryBroker()

    async def start(self):
        """Start the broker if needed."""
        await self.broker.start()
        logger.info(
            f"Started {getattr(self.config, 'broker_type', 'redis')} broker")

    async def stop(self):
        """Stop the broker."""
        await self.broker.close()
        logger.info(
            f"Stopped {getattr(self.config, 'broker_type', 'redis')} broker")

    async def publish_event(
        self, event_type: str, data: Dict[str, Any], routing_key: Optional[str] = None
    ) -> None:
        """
        Publish a payment event.

        Args:
            event_type: Type of event (e.g., payment.created)
            data: Event data
            routing_key: Optional custom routing key
        """
        message = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        # Use event_type as routing key if not provided
        routing_key = routing_key or event_type

        broker_type = getattr(self.config, "broker_type", "redis")

        try:
            if broker_type == "rabbitmq" and hasattr(self, "exchange_name"):
                await self.broker.publish(
                    message,
                    routing_key=routing_key,
                    exchange=self.exchange_name,
                    **self.exchange_settings,
                )

            elif broker_type == "kafka" and hasattr(self, "topic_prefix"):
                topic = f"{self.topic_prefix}{routing_key.replace('.', '_')}"
                await self.broker.publish(message, topic=topic)

            elif broker_type == "redis" or hasattr(self, "stream_maxlen"):
                stream = f"{getattr(self.config, 'exchange_name', 'payments')}:{routing_key.replace('.', ':')}"
                await self.broker.publish(
                    message, stream=stream, maxlen=self.stream_maxlen
                )

            elif broker_type == "nats" and hasattr(self, "subject_prefix"):
                subject = f"{self.subject_prefix}{routing_key.replace('.', '.')}"
                await self.broker.publish(message, subject=subject)

            else:  # Use the generic method for our in-memory broker or any other case
                await self.broker.publish(message, routing_key=routing_key)

            logger.debug(f"Published event {event_type} with routing key {routing_key}")

        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {str(e)}")
            # Consider implementing retry logic here
            raise
