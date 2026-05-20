from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.product import Product, ProductBrand, ProductTypeCatalog
from app.services.product_dictionary_service import ProductDictionaryService


def test_product_dictionary_service_links_product_catalog_fields(db_session: Session) -> None:
    product = Product(
        item_code="ERP-1",
        name="First",
        brand=" Brand A ",
        trade_mark="Mark A",
        product_type="Food",
        is_active=True,
    )
    db_session.add(product)

    ProductDictionaryService(db_session).sync_product(product)
    db_session.flush()

    assert product.brand == "Brand A"
    assert product.trade_mark == "Mark A"
    assert product.product_type == "food"
    assert product.brand_id is not None
    assert product.trade_mark_id is not None
    assert product.product_type_id is not None


def test_product_dictionary_service_renames_linked_products(db_session: Session) -> None:
    product = Product(
        item_code="ERP-1",
        name="First",
        brand="Brand A",
        product_type="Food",
        is_active=True,
    )
    db_session.add(product)
    service = ProductDictionaryService(db_session)
    service.sync_product(product)
    db_session.flush()

    brand = db_session.get(ProductBrand, product.brand_id)
    product_type = db_session.get(ProductTypeCatalog, product.product_type_id)
    assert brand is not None
    assert product_type is not None

    service.update_dictionary_item(brand, name="Brand B")
    service.update_dictionary_item(product_type, name="NonFood", normalize_as_type=True)
    db_session.flush()

    assert product.brand == "Brand B"
    assert product.product_type == "nonfood"


def test_product_dictionary_service_updates_product_type_warehouse_no(db_session: Session) -> None:
    product_type = ProductTypeCatalog(
        name="food",
        normalized_name="food",
        warehouse_no=None,
        is_active=True,
    )
    db_session.add(product_type)
    db_session.flush()

    ProductDictionaryService(db_session).update_dictionary_item(product_type, warehouse_no=" 12 ")
    db_session.flush()

    assert product_type.warehouse_no == "12"
