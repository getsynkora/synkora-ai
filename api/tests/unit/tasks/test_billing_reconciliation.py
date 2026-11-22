from unittest.mock import MagicMock

from src.tasks.billing_tasks import _find_missing_deductions


def test_messages_of_pool_plans_are_not_reported_as_missing_deductions():
    """Reproduces the daily job re-queuing every pool-plan message and counting it a second time."""
    db = MagicMock()
    db.execute.return_value = []
    _find_missing_deductions(db)
    sql = " ".join(str(db.execute.call_args[0][0]).split())

    assert "NOT EXISTS ( SELECT 1 FROM credit_transactions" in sql
    assert "FROM tenant_subscriptions ts JOIN subscription_plans sp" in sql
    assert "ts.tenant_id = a.tenant_id" in sql
    assert "ts.status IN ('ACTIVE', 'TRIAL')" in sql
    # A plan without pools may store JSON null, which must not exclude its tenant
    # jsonb_array_length errors on JSON null, so it only runs once the value is known to be an array
    assert (
        "CASE WHEN jsonb_typeof(sp.quota_pools) = 'array' THEN jsonb_array_length(sp.quota_pools) > 0 ELSE false END"
        in sql
    )
