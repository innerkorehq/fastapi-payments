import json
import logging
from urllib.parse import parse_qsl
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
from fastapi import BackgroundTasks
from pydantic import BaseModel, Field, EmailStr

from ..schemas.payment import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    PaymentMethodCreate,
    PaymentMethodResponse,
        PaymentMethodUpdate,
    ProductCreate,
    ProductResponse,
    PlanCreate,
    PlanResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    PaymentCreate,
    PaymentResponse,
    SyncJobResponse,
    SyncRequest,
    SyncResult,
)
from ..services.payment_service import PaymentService
from .dependencies import get_payment_service_with_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search by name or email"),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """Return stored customers."""

    return await payment_service.list_customers(
        limit=limit, offset=offset, search=search
    )


@router.post("/customers", response_model=CustomerResponse)
async def create_customer(
    customer: CustomerCreate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Create a new customer."""
    try:
        result = await payment_service.create_customer(
            email=customer.email,
            name=customer.name,
            meta_info=customer.meta_info,
            address=getattr(customer, "address", None),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


    @router.patch("/customers/{customer_id}", response_model=CustomerResponse)
    async def update_customer(
        customer_id: str,
        customer_update: "CustomerUpdate",
        payment_service: PaymentService = Depends(get_payment_service_with_db),
    ) -> Dict[str, Any]:
        """Update an existing customer."""
        try:
            result = await payment_service.update_customer(
                customer_id,
                email=getattr(customer_update, "email", None),
                name=getattr(customer_update, "name", None),
                meta_info=getattr(customer_update, "meta_info", None),
                address=getattr(customer_update, "address", None),
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
        payload = payment_method.model_dump(exclude_none=True)
        provider = payload.pop("provider", None)
        result = await payment_service.create_payment_method(
            customer_id=customer_id,
            payment_details=payload,
            provider=provider,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch(
    "/customers/{customer_id}/payment-methods/{method_id}",
    response_model=PaymentMethodResponse,
)
async def update_payment_method(
    customer_id: str,
    method_id: str,
    payload: PaymentMethodUpdate,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Update stored payment method (e.g., set default, update meta)."""
    try:
        result = await payment_service.update_payment_method(
            customer_id=customer_id, method_id=method_id, **payload.model_dump(exclude_none=True)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/customers/{customer_id}/payment-methods/{method_id}/default",
    response_model=PaymentMethodResponse,
)
async def set_default_payment_method(
    customer_id: str,
    method_id: str,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Mark the stored payment method as default for this customer."""
    try:
        result = await payment_service.set_default_payment_method(
            customer_id=customer_id, method_id=method_id
        )
        # normalize to PaymentMethodResponse fields
        return {
            "id": result["id"],
            "provider": result.get("provider"),
            "type": "card",
            "is_default": result.get("is_default", False),
            "card": None,
            "mandate_id": None,
            "created_at": None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/customers/{customer_id}/payment-methods/{method_id}",
    response_model=Dict[str, Any],
)
async def delete_payment_method(
    customer_id: str,
    method_id: str,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Delete/detach a saved payment method for the customer."""
    try:
        result = await payment_service.delete_payment_method(
            customer_id=customer_id, method_id=method_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/customers/{customer_id}/payment-methods",
    response_model=List[PaymentMethodResponse],
)
async def list_payment_methods(
    customer_id: str,
    provider: Optional[str] = Query(None, description="Filter by provider name"),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """List payment methods for a customer."""
    result = await payment_service.list_payment_methods(customer_id, provider=provider)
    return result


@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """Return stored products."""

    return await payment_service.list_products(limit=limit, offset=offset)


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


@router.get("/plans", response_model=List[PlanResponse])
async def list_plans(
    product_id: Optional[str] = Query(
        None, description="Filter plans for a specific product"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """Return price plans."""

    return await payment_service.list_plans(
        product_id=product_id, limit=limit, offset=offset
    )


@router.get(
    "/products/{product_id}/plans", response_model=List[PlanResponse]
)
async def list_product_plans(
    product_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """Return plans belonging to a product."""

    return await payment_service.list_plans(
        product_id=product_id, limit=limit, offset=offset
    )


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


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    customer_id: Optional[str] = Query(
        None, description="Filter by customer ID"
    ),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """Return subscriptions."""

    return await payment_service.list_subscriptions(
        customer_id=customer_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/customers/{customer_id}/subscriptions", response_model=List[SubscriptionResponse]
)
async def list_customer_subscriptions(
    customer_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """Return subscriptions for a specific customer."""

    return await payment_service.list_subscriptions(
        customer_id=customer_id,
        limit=limit,
        offset=offset,
    )


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


@router.get("/payments", response_model=List[PaymentResponse])
async def list_payments(
    customer_id: Optional[str] = Query(
        None, description="Filter by customer ID"
    ),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> List[Dict[str, Any]]:
    """Return processed payments."""

    return await payment_service.list_payments(
        customer_id=customer_id,
        status=status,
        limit=limit,
        offset=offset,
    )

@router.post("/sync", response_model=SyncJobResponse)
async def sync_resources(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    """Synchronize local database entities with provider state.

    You can request a subset of resources to sync by providing `resources`.
    Supported names: customers, products, plans, payments, subscriptions, payment_methods.
    """
    try:
        # Create a job record and schedule background execution; return job id
        job = await payment_service.create_sync_job(
            resources=request.resources, provider=request.provider, filters=request.filters
        )

        # schedule background execution of the job
        background_tasks.add_task(payment_service.execute_sync_job, job["id"])

        return job
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/{job_id}", response_model=SyncJobResponse)
async def get_sync_job(
    job_id: str,
    payment_service: PaymentService = Depends(get_payment_service_with_db),
) -> Dict[str, Any]:
    job = await payment_service.sync_job_repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return {
        "id": job.id,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "result": job.result,
    }


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
            mandate_id=getattr(payment, 'mandate_id', None),
            payment_method_id=payment.payment_method_id,
            description=payment.description,
            meta_info=payment.meta_info,
            provider=payment.provider,
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
        body_bytes = await request.body()
        payload: Dict[str, Any]
        if body_bytes:
            body_text = body_bytes.decode()
            try:
                payload = json.loads(body_text)
            except json.JSONDecodeError:
                payload = {k: v for k, v in parse_qsl(body_text)}
        else:
            payload = {}
        result = await payment_service.handle_webhook(
            provider=provider, payload=payload, signature=signature
        )
        return {"status": "success", "event_type": result.get("event_type")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
