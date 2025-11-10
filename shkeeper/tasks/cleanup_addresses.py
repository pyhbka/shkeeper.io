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
        for invoice in expired_invoices:
            # Освобождаем адрес
            InvoiceAddress.release_address(invoice.addr)
            released_count += 1

        db.session.commit()
        app.logger.info(f"Released {released_count} expired addresses")
        return released_count

if __name__ == "__main__":
    cleanup_expired_addresses()
