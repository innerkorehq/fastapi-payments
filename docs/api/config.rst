Configuration API
================

Configuration Schema
------------------

.. code-block:: python

   from fastapi_payments.config.config_schema import PaymentConfig
   
   # Example usage
   config = PaymentConfig(**config_dict)

PaymentConfig
^^^^^^^^^^^

.. autoclass:: fastapi_payments.config.config_schema.PaymentConfig
   :members:
   :undoc-members:
   :show-inheritance:

ProviderConfig
^^^^^^^^^^^^

.. autoclass:: fastapi_payments.config.config_schema.ProviderConfig
   :members:
   :undoc-members:
   :show-inheritance:

DatabaseConfig
^^^^^^^^^^^^

.. autoclass:: fastapi_payments.config.config_schema.DatabaseConfig
   :members:
   :undoc-members:
   :show-inheritance:

RabbitMQConfig
^^^^^^^^^^^^

.. autoclass:: fastapi_payments.config.config_schema.RabbitMQConfig
   :members:
   :undoc-members:
   :show-inheritance:

PricingConfig
^^^^^^^^^^^

.. autoclass:: fastapi_payments.config.config_schema.PricingConfig
   :members:
   :undoc-members:
   :show-inheritance:

TaxConfig
^^^^^^^^

.. autoclass:: fastapi_payments.config.config_schema.TaxConfig
   :members:
   :undoc-members:
   :show-inheritance:

Configuration Functions
--------------------

load_config
^^^^^^^^^^

.. autofunction:: fastapi_payments.config.settings.load_config

load_config_from_file
^^^^^^^^^^^^^^^^^^^^

.. autofunction:: fastapi_payments.config.settings.load_config_from_file

load_config_from_env
^^^^^^^^^^^^^^^^^^

.. autofunction:: fastapi_payments.config.settings.load_config_from_env

merge_configs
^^^^^^^^^^^

.. autofunction:: fastapi_payments.config.settings.merge_configs