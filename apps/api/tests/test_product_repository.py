from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.product import Product
from app.repositories.products import ProductRepository


def test_product_repository_filters_and_sorts(db_session: Session) -> None:
    db_session.add_all(
        [
            Product(
                item_code="ERP-2",
                name="Second",
                brand="Brand B",
                trade_mark="Mark B",
                product_type="food",
                is_active=True,
                exclude_from_export=False,
            ),
            Product(
                item_code="ERP-1",
                name="First",
                brand="Brand A",
                trade_mark="Mark A",
                product_type="nonfood",
                is_active=True,
                exclude_from_export=True,
            ),
            Product(
                item_code="ERP-3",
                name="Third",
                brand="Brand A",
                trade_mark="Mark A",
                product_type="food",
                is_active=False,
                exclude_from_export=False,
            ),
        ]
    )
    db_session.flush()

    products = ProductRepository(db_session).list(
        product_type="food",
        is_active=True,
        sort_by="item_code",
        sort_dir="desc",
    )

    assert [product.item_code for product in products] == ["ERP-2"]


def test_product_repository_filters_export_exclusion_and_brand(db_session: Session) -> None:
    db_session.add_all(
        [
            Product(
                item_code="ERP-1",
                name="First",
                brand="Brand A",
                product_type="food",
                is_active=True,
                exclude_from_export=True,
            ),
            Product(
                item_code="ERP-2",
                name="Second",
                brand="Brand A",
                product_type="food",
                is_active=True,
                exclude_from_export=False,
            ),
        ]
    )
    db_session.flush()

    products = ProductRepository(db_session).list(
        brand="Brand A",
        exclude_from_export=True,
    )

    assert [product.item_code for product in products] == ["ERP-1"]


def test_product_repository_filters_product_type_case_insensitive(db_session: Session) -> None:
    db_session.add(
        Product(
            item_code="ERP-1",
            name="First",
            product_type="flint",
            is_active=True,
        )
    )
    db_session.flush()

    products = ProductRepository(db_session).list(product_type="Flint")

    assert [product.item_code for product in products] == ["ERP-1"]


def test_product_repository_filters_by_branch(db_session: Session) -> None:
    db_session.add_all(
        [Branch(id=1, name="Branch 1", is_active=True), Branch(id=2, name="Branch 2", is_active=True)]
    )
    db_session.flush()
    db_session.add_all(
        [
            Product(branch_id=1, item_code="ERP-1", name="First branch", is_active=True),
            Product(branch_id=2, item_code="ERP-2", name="Second branch", is_active=True),
        ]
    )
    db_session.flush()

    products = ProductRepository(db_session, branch_id=2).list()

    assert [product.item_code for product in products] == ["ERP-2"]


def test_product_repository_search_ignores_case_for_product_name(db_session: Session) -> None:
    db_session.add_all(
        [
            Product(
                item_code="ERP-1",
                name="КОНФЕТЫ ШОКОЛАДНЫЕ",
                is_active=True,
            ),
            Product(
                item_code="ERP-2",
                name="Печенье",
                is_active=True,
            ),
        ]
    )
    db_session.flush()

    products = ProductRepository(db_session).list(search="конфеты")

    assert [product.item_code for product in products] == ["ERP-1"]


def test_product_repository_search_ignores_case_for_item_code(db_session: Session) -> None:
    db_session.add(
        Product(
            item_code="ERP-Case-1",
            name="Product",
            is_active=True,
        )
    )
    db_session.flush()

    products = ProductRepository(db_session).list(search="erp-case")

    assert [product.item_code for product in products] == ["ERP-Case-1"]
