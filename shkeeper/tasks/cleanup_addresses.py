"""
Фоновая задача для обработки истекших инвойсов
Запускается каждый час через cron или celery

Логика:
- Инвойс истекает (EXPIRED) через 1 час после создания
- Адрес освобождается через 1.5 часа после создания инвойса
"""

from datetime import datetime, timedelta
from shkeeper import app, db
from shkeeper.models import Invoice, InvoiceAddress, InvoiceStatus


def cleanup_expired_invoices():
    """
    Двухэтапная обработка истекших инвойсов:
    1. Помечает инвойсы как EXPIRED через 1 час
    2. Освобождает адреса через 1.5 часа
    """
    with app.app_context():
        expired_count = mark_invoices_expired()
        released_count = release_expired_addresses()
        return {"expired": expired_count, "released": released_count}


def mark_invoices_expired():
    """
    Помечает неоплаченные инвойсы старше 1 часа как EXPIRED
    """
    expire_threshold = datetime.utcnow() - timedelta(hours=1)

    # Обновляем статус напрямую в базе без загрузки объектов
    updated_count = Invoice.query.filter(
        Invoice.status == InvoiceStatus.UNPAID,
        Invoice.created_at < expire_threshold
    ).update({Invoice.status: InvoiceStatus.EXPIRED}, synchronize_session=False)

    db.session.commit()
    app.logger.info(f"Marked {updated_count} invoices as EXPIRED")
    return updated_count


def release_expired_addresses():
    """
    Освобождает адреса для EXPIRED инвойсов старше 1.5 часа
    """
    release_threshold = datetime.utcnow() - timedelta(hours=1, minutes=30)

    # Находим EXPIRED инвойсы старше 1.5 часа, у которых есть привязанный адрес в InvoiceAddress
    invoices_to_release = Invoice.query.filter(
        Invoice.status == InvoiceStatus.EXPIRED,
        Invoice.created_at < release_threshold,
        Invoice.id.in_(
            db.session.query(InvoiceAddress.invoice_id).filter(
                InvoiceAddress.invoice_id.isnot(None)
            )
        )
    ).all()

    released_count = 0
    error_count = 0
    for invoice in invoices_to_release:
        try:
            InvoiceAddress.release_address(invoice.addr)
            released_count += 1
            app.logger.debug(f"Released address {invoice.addr} from invoice {invoice.id}")
        except Exception as e:
            error_count += 1
            app.logger.error(f"Failed to release address {invoice.addr} for invoice {invoice.id}: {e}")
            continue

    db.session.commit()
    app.logger.info(f"Released {released_count} addresses, errors: {error_count}")
    return released_count


# Backward compatibility alias
cleanup_expired_addresses = cleanup_expired_invoices


if __name__ == "__main__":
    cleanup_expired_invoices()
