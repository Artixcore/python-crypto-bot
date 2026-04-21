from crypto_bot.execution.order_router import new_client_order_id


def test_client_order_id_length():
    cid = new_client_order_id("s1", "e1")
    assert len(cid) <= 36
    assert cid.isalnum()
