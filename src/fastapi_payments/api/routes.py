from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Header,
    Body,
    Query,
    Path,
)
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, EmailStr
import logging

from ..schemas.payment import (
    CustomerCreate,
    CustomerResponse,
    PaymentMethodCreate,
    PaymentMethodResponse,
    ProductCreate,
    ProductResponse,
    PlanCreate,
    PlanResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    PaymentCreate,
    PaymentResponse,
)
from ..services.payment_service import PaymentService
from .dependencies import get_payment_service_with_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])


@router.post("/customers", response_model=CustomerResponse)
async def create_customer(
    customer: CustomerCreate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Create a new customer."""
    try:
        result = await payment_service.create_customer(
            email=customer.email, name=customer.name, meta_info=customer.meta_info
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str = Path(..., title="Customer ID"),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Get customer details."""
    result = await payment_service.get_customer(customer_id)
    if not result:
        raise HTTPException(status_code=404, detail="Customer not found")
    return result


@router.post(
    "/customers/{customer_id}/payment-methods", response_model=PaymentMethodResponse
)
async def create_payment_method(
    customer_id: str,
    payment_method: PaymentMethodCreate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Add a payment method to a customer."""
    try:
        result = await payment_service.create_payment_method(
            customer_id=customer_id,
            # Update from dict() to model_dump()
            payment_details=payment_method.model_dump(),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/customers/{customer_id}/payment-methods",
    response_model=List[PaymentMethodResponse],
)
async def list_payment_methods(
    customer_id: str,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """List payment methods for a customer."""
    result = await payment_service.list_payment_methods(customer_id)
    return result


@router.post("/products", response_model=ProductResponse)
async def create_product(
    product: ProductCreate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Create a new product."""
    try:
        result = await payment_service.create_product(
            name=product.name,
            description=product.description,
            meta_info=product.meta_info,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/products/{product_id}/plans", response_model=PlanResponse)
async def create_plan(
    product_id: str,
    plan: PlanCreate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Create a new price plan for a product."""
    try:
        result = await payment_service.create_plan(
            product_id=product_id,
            name=plan.name,
            description=plan.description,
            pricing_model=plan.pricing_model,
            amount=plan.amount,
            currency=plan.currency,
            billing_interval=plan.billing_interval,
            billing_interval_count=plan.billing_interval_count,
            trial_period_days=plan.trial_period_days,
            meta_info=plan.meta_info,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/customers/{customer_id}/subscriptions", response_model=SubscriptionResponse
)
async def create_subscription(
    customer_id: str,
    subscription: SubscriptionCreate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Subscribe a customer to a plan."""
    try:
        result = await payment_service.create_subscription(
            customer_id=customer_id,
            plan_id=subscription.plan_id,
            quantity=subscription.quantity,
            trial_period_days=subscription.trial_period_days,
            meta_info=subscription.meta_info,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: str,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Get subscription details."""
    result = await payment_service.get_subscription(subscription_id)
    if not result:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return result


@router.post("/subscriptions/{subscription_id}/cancel", response_model=Dict[str, Any])
async def cancel_subscription(
    subscription_id: str,
    cancel_at_period_end: bool = True,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Cancel a subscription."""
    try:
        result = await payment_service.cancel_subscription(
            subscription_id=subscription_id, cancel_at_period_end=cancel_at_period_end
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payments", response_model=PaymentResponse)
async def process_payment(
    payment: PaymentCreate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Process a one-time payment."""
    try:
        result = await payment_service.process_payment(
            customer_id=payment.customer_id,
            amount=payment.amount,
            currency=payment.currency,
            payment_method_id=payment.payment_method_id,
            description=payment.description,
            meta_info=payment.meta_info,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payments/{payment_id}/refund", response_model=Dict[str, Any])
async def refund_payment(
    payment_id: str,
    amount: Optional[float] = None,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Refund a payment."""
    try:
        result = await payment_service.refund_payment(
            payment_id=payment_id, amount=amount
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhooks/{provider}", response_model=Dict[str, Any])
async def handle_webhook(
    provider: str,
    request: Request,
    signature: Optional[str] = Header(None),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Handle webhooks from payment providers."""
    try:
        payload = await request.json()
        result = await payment_service.handle_webhook(
            provider=provider, payload=payload, signature=signature
        )
        return {"status": "success", "event_type": result.get("event_type")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
