Database Architecture
==================

Data Model
---------

FastAPI Payments uses SQLAlchemy models to store payment-related data. The core models include:

Customer
^^^^^^^

.. code-block:: python

   class Customer(Base):
       __tablename__ = "customers"
       
       id = Column(String, primary_key=True, default=generate_uuid)
       external_id = Column(String, nullable=True, unique=True)
       email = Column(String, nullable=False)
       name = Column(String)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
       metadata = Column(JSON, nullable=True)
       
       provider_customers = relationship("ProviderCustomer", back_populates="customer")
       subscriptions = relationship("Subscription", back_populates="customer")
       payments = relationship("Payment", back_populates="customer")

The Customer model stores basic customer information and links to provider-specific customer IDs.

ProviderCustomer
^^^^^^^^^^^^^^

.. code-block:: python

   class ProviderCustomer(Base):
       __tablename__ = "provider_customers"
       
       id = Column(String, primary_key=True, default=generate_uuid)
       customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
       provider = Column(String, nullable=False)  # stripe, paypal, etc.
       provider_customer_id = Column(String, nullable=False)
       created_at = Column(DateTime, default=datetime.utcnow)
       
       customer = relationship("Customer", back_populates="provider_customers")

The ProviderCustomer model maps internal customers to provider-specific identifiers.

Product
^^^^^^

.. code-block:: python

   class Product(Base):
       __tablename__ = "products"
       
       id = Column(String, primary_key=True, default=generate_uuid)
       name = Column(String, nullable=False)
       description = Column(Text)
       active = Column(Boolean, default=True)
       metadata = Column(JSON, nullable=True)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
       
       plans = relationship("Plan", back_populates="product")

The Product model represents items or services that customers can purchase.

Plan
^^^^

.. code-block:: python

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
       metadata = Column(JSON, nullable=True)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
       
       product = relationship("Product", back_populates="plans")
       subscriptions = relationship("Subscription", back_populates="plan")
       features = relationship("PlanFeature", back_populates="plan")
       tiers = relationship("PricingTier", back_populates="plan")

The Plan model defines pricing plans for products, with support for various pricing models.

Subscription
^^^^^^^^^^^

.. code-block:: python

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
       metadata = Column(JSON, nullable=True)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
       
       customer = relationship("Customer", back_populates="subscriptions")
       plan = relationship("Plan", back_populates="subscriptions")
       usage_records = relationship("UsageRecord", back_populates="subscription")
       invoices = relationship("Invoice", back_populates="subscription")

The Subscription model represents a customer's subscription to a specific plan.

Payment
^^^^^^

.. code-block:: python

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
       payment_method = Column(String, nullable=True)  # credit_card, bank_transfer, etc.
       error_message = Column(String, nullable=True)
       refunded_amount = Column(Float, default=0.0)
       metadata = Column(JSON, nullable=True)
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
       
       customer = relationship("Customer", back_populates="payments")
       invoice = relationship("Invoice", back_populates="payments")

The Payment model tracks payment transactions, including status and refunds.

Repository Pattern
---------------

FastAPI Payments uses repositories to abstract database operations:

.. code-block:: python

   # Example repository usage
   customer_repo = CustomerRepository(db_session)
   
   # Create a customer
   customer = await customer_repo.create(
       email="customer@example.com",
       name="John Doe"
   )
   
   # Find a customer by email
   customer = await customer_repo.get_by_email("customer@example.com")
   
   # Update a customer
   await customer_repo.update(
       customer.id,
       name="John Smith"
   )

Available repositories:

- ``CustomerRepository``: Customer operations
- ``ProductRepository``: Product operations
- ``PlanRepository``: Plan operations
- ``SubscriptionRepository``: Subscription operations
- ``PaymentRepository``: Payment operations
- ``InvoiceRepository``: Invoice operations

Database Configuration
-------------------

Configure the database connection in your settings:

.. code-block:: json

   {
     "database": {
       "url": "postgresql+asyncpg://user:password@localhost/payments",
       "echo": false,
       "pool_size": 5,
       "max_overflow": 10
     }
   }

Supported databases:

- PostgreSQL (recommended): ``postgresql+asyncpg://user:password@localhost/payments``
- MySQL: ``mysql+aiomysql://user:password@localhost/payments``
- SQLite: ``sqlite+aiosqlite:///./payments.db``

Migrations
---------

For production use, manage database migrations with Alembic:

.. code-block:: bash

   # Install alembic
   pip install alembic
   
   # Initialize alembic
   alembic init migrations
   
   # Configure alembic to use your models
   # Edit migrations/env.py to import your models
   
   # Create a migration
   alembic revision --autogenerate -m "Initial payment tables"
   
   # Run the migration
   alembic upgrade head
   
   # Rollback if needed
   alembic downgrade -1