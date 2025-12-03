"""
Фоновая задача для освобождения адресов с истекшим сроком
Запускается каждый час через cron или celery
"""

from datetime import datetime, timedelta
from shkeeper import app, db
from shkeeper.models import Invoice, InvoiceAddress, InvoiceStatus

def cleanup_expired_addresses():
    """
    Освобождает адреса (invoice_id = NULL) для неоплаченных инвойсов старше 1.5 часа
    """
    with app.app_context():
        threshold_time = datetime.utcnow() - timedelta(hours=1, minutes=30)

        # Находим все неоплаченные инвойсы старше 1.5 часа
        expired_invoices = Invoice.query.filter(
            Invoice.status == InvoiceStatus.UNPAID,
            Invoice.created_at < threshold_time
        ).all()

        released_count = 0
        error_count = 0
        for invoice in expired_invoices:
            # Проверяем наличие адреса
            if not invoice.addr:
                app.logger.debug(f"Invoice {invoice.id} has no address, skipping")
                continue

            try:
                # Освобождаем адрес
                InvoiceAddress.release_address(invoice.addr)
                released_count += 1
                app.logger.debug(f"Released address {invoice.addr} from invoice {invoice.id}")
            except Exception as e:
                error_count += 1
                app.logger.error(f"Failed to release address {invoice.addr} for invoice {invoice.id}: {e}")
                continue

        db.session.commit()
        app.logger.info(f"Released {released_count} expired addresses, errors: {error_count}")
        return released_count

if __name__ == "__main__":
    cleanup_expired_addresses()
