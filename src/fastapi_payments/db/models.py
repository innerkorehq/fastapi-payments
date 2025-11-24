from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, timezone
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CANCELED = "canceled"
    EXPIRED = "expired"


class PricingModel(enum.Enum):
    SUBSCRIPTION = "subscription"
    USAGE_BASED = "usage_based"
    TIERED = "tiered"
    PER_USER = "per_user"
    FREEMIUM = "freemium"
    DYNAMIC = "dynamic"
    HYBRID = "hybrid"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=generate_uuid)
    external_id = Column(String, nullable=True, unique=True)
    email = Column(String, nullable=False)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    meta_info = Column(JSON, nullable=True)
    # First-class address field stored as JSON (line1, line2, city, state, postal_code, country)
    address = Column(JSON, nullable=True)

    provider_customers = relationship(
        "ProviderCustomer", back_populates="customer")
    subscriptions = relationship("Subscription", back_populates="customer")
    payments = relationship("Payment", back_populates="customer")
    # Stored payment methods saved on the platform for this customer
    payment_methods = relationship("PaymentMethod", back_populates="customer")


class ProviderCustomer(Base):
    __tablename__ = "provider_customers"

    id = Column(String, primary_key=True, default=generate_uuid)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    provider = Column(String, nullable=False)  # stripe, paypal, etc.
    provider_customer_id = Column(String, nullable=False)

    customer = relationship("Customer", back_populates="provider_customers")


class SyncJob(Base):
    """Represents an asynchronous synchronization job request."""

    __tablename__ = "sync_jobs"

    id = Column(String, primary_key=True, default=lambda: f"job_{uuid.uuid4().hex[:8]}")
    status = Column(String, nullable=False, default="queued")
    resources = Column(JSON, nullable=True)
    provider = Column(String, nullable=True)
    filters = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    __table_args__ = ({"sqlite_autoincrement": True},)


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    description = Column(Text)
    active = Column(Boolean, default=True)
    meta_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    plans = relationship("Plan", back_populates="product")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True, default=generate_uuid)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    pricing_model = Column(Enum(PricingModel), nullable=False)
    amount = Column(Float)
    currency = Column(String, default="USD")
    billing_interval = Column(String)  # monthly, yearly, etc.
    billing_interval_count = Column(Integer, default=1)
    trial_period_days = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    meta_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    product = relationship("Product", back_populates="plans")
    subscriptions = relationship("Subscription", back_populates="plan")
    features = relationship("PlanFeature", back_populates="plan")
    tiers = relationship("PricingTier", back_populates="plan")


class PlanFeature(Base):
    __tablename__ = "plan_features"

    id = Column(String, primary_key=True, default=generate_uuid)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    name = Column(String, nullable=False)
    value = Column(String)
    description = Column(Text)

    plan = relationship("Plan", back_populates="features")


class PricingTier(Base):
    __tablename__ = "pricing_tiers"

    id = Column(String, primary_key=True, default=generate_uuid)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    name = Column(String, nullable=True)
    lower_bound = Column(Float, nullable=False)  # Start of tier
    # End of tier (null = unlimited)
    upper_bound = Column(Float, nullable=True)
    # Price per unit in this tier
    price_per_unit = Column(Float, nullable=False)
    flat_fee = Column(Float, default=0.0)  # Flat fee for this tier

    plan = relationship("Plan", back_populates="tiers")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, default=generate_uuid)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    provider = Column(String, nullable=False)  # stripe, paypal, etc.
    provider_subscription_id = Column(String, nullable=True)
    status = Column(String, nullable=False)  # active, canceled, etc.
    quantity = Column(Integer, default=1)  # For per-seat pricing
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    canceled_at = Column(DateTime, nullable=True)
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    meta_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    usage_records = relationship("UsageRecord", back_populates="subscription")
    invoices = relationship("Invoice", back_populates="subscription")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(String, primary_key=True, default=generate_uuid)
    subscription_id = Column(String, ForeignKey(
        "subscriptions.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))
    description = Column(String, nullable=True)
    meta_info = Column(JSON, nullable=True)

    subscription = relationship("Subscription", back_populates="usage_records")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=generate_uuid)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    subscription_id = Column(String, ForeignKey(
        "subscriptions.id"), nullable=True)
    provider = Column(String, nullable=False)
    provider_invoice_id = Column(String, nullable=True)
    # draft, open, paid, uncollectible, void
    status = Column(String, nullable=False)
    currency = Column(String, default="USD")
    total_amount = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    customer = relationship("Customer", backref="invoices")
    subscription = relationship("Subscription", back_populates="invoices")
    invoice_items = relationship("InvoiceItem", back_populates="invoice")
    payments = relationship("Payment", back_populates="invoice")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    quantity = Column(Float, default=1)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    # subscription, one-time, tax, discount
    type = Column(String, nullable=True)

    invoice = relationship("Invoice", back_populates="invoice_items")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=generate_uuid)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=True)
    provider = Column(String, nullable=False)  # stripe, paypal, etc.
    provider_payment_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(Enum(PaymentStatus), nullable=False)
    # credit_card, bank_transfer, etc.
    payment_method = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    refunded_amount = Column(Float, default=0.0)
    meta_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    customer = relationship("Customer", back_populates="payments")
    invoice = relationship("Invoice", back_populates="payments")


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(String, primary_key=True, default=generate_uuid)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    provider = Column(String, nullable=False)
    # ID of the payment method in the provider (e.g. pm_... for Stripe)
    provider_payment_method_id = Column(String, nullable=False)
    # Optional mandate id (created via SetupIntent flows in providers like Stripe)
    mandate_id = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)

    # Basic card metadata for convenience & searching (may be null for non-card methods)
    card_brand = Column(String, nullable=True)
    card_last4 = Column(String, nullable=True)
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)

    meta_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    customer = relationship("Customer", back_populates="payment_methods")
