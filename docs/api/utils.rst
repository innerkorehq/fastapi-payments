Utilities API
============

Exception Classes
---------------

.. autoclass:: fastapi_payments.utils.exceptions.PaymentError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: fastapi_payments.utils.exceptions.ProviderError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: fastapi_payments.utils.exceptions.ConfigurationError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: fastapi_payments.utils.exceptions.ValidationError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: fastapi_payments.utils.exceptions.ResourceNotFoundError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: fastapi_payments.utils.exceptions.AuthenticationError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: fastapi_payments.utils.exceptions.WebhookError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: fastapi_payments.utils.exceptions.PaymentRequiresActionError
   :members:
   :undoc-members:
   :show-inheritance:

Helper Functions
--------------

.. autofunction:: fastapi_payments.utils.helpers.generate_random_string

.. autofunction:: fastapi_payments.utils.helpers.generate_idempotency_key

.. autofunction:: fastapi_payments.utils.helpers.format_amount

.. autofunction:: fastapi_payments.utils.helpers.parse_amount

.. autofunction:: fastapi_payments.utils.helpers.sanitize_metadata

.. autofunction:: fastapi_payments.utils.helpers.calculate_subscription_period_end