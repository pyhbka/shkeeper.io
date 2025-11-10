# Реализация ротации адресов для API /api/v1/<crypto_name>/payment_request

## Найденные куски кода

### 1. API Endpoint - shkeeper/api_v1.py:90-128

**Текущий код:**
```python
@bp.post("/<crypto_name>/payment_request")
@api_key_required
def payment_request(crypto_name):
    try:
        try:
            crypto = Crypto.instances[crypto_name]
        except KeyError:
            return {
                "status": "error",
                "message": f"{crypto_name} payment gateway is unavailable",
            }
        if not crypto.wallet.enabled:
            return {
                "status": "error",
                "message": f"{crypto_name} payment gateway is unavailable",
            }
        if app.config.get("DISABLE_CRYPTO_WHEN_LAGS") and crypto.getstatus() != "Synced":
            return {
                "status": "error",
                "message": f"{crypto_name} payment gateway is unavailable because of lagging",
            }

        req = request.get_json(force=True)
        invoice = Invoice.add(crypto=crypto, request=req)
        response = {
            "status": "success",
            **invoice.for_response(),
        }
        app.logger.info({"request": req, "response": response})

    except Exception as e:
        app.logger.exception(f"Failed to create invoice for {req}")
        response = {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
        }

    return response
```

**Изменения:**
Без изменений - вся логика в Invoice.add()

---

### 2. Модель InvoiceAddress - shkeeper/models.py:642-648

**Текущий код:**
```python
class InvoiceAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)
    crypto = db.Column(db.String)
    addr = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    __table_args__ = (db.UniqueConstraint("invoice_id", "crypto", "addr"),)
```

**Изменения:**
```python
class InvoiceAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=True)  # ИЗМЕНЕНО: nullable=True
    crypto = db.Column(db.String, index=True)  # ДОБАВЛЕН: index=True
    addr = db.Column(db.String, index=True)  # ДОБАВЛЕН: index=True
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    __table_args__ = (
        db.Index('ix_invoice_address_crypto_invoice_id', 'crypto', 'invoice_id'),
    )

    @classmethod
    def get_free_address(cls, crypto, amount_crypto=None):
        """
        Получить свободный адрес из пула (invoice_id = NULL) или создать новый
        """
        from datetime import datetime, timedelta

        # Для Lightning проверяем сумму
        if "LIGHTNING" in crypto.crypto:
            if amount_crypto is None:
                # Создаем новый
                new_addr = crypto.mkaddr(details={"value": amount_crypto})
                return new_addr

            # Ищем свободный Lightning адрес с точной суммой
            threshold_time = datetime.utcnow() - timedelta(hours=1, minutes=30)

            free_addr = db.session.query(cls.addr).join(
                Invoice, cls.addr == Invoice.addr
            ).filter(
                cls.crypto == crypto.crypto,
                cls.invoice_id == None,  # Свободный
                Invoice.amount_crypto == amount_crypto,  # ТОЧНОЕ совпадение суммы
                Invoice.created_at < threshold_time  # Старше 1.5 часа
            ).with_for_update(skip_locked=True).first()

            if free_addr:
                return free_addr[0]

            # Создаем новый
            new_addr = crypto.mkaddr(details={"value": amount_crypto})
            return new_addr

        # Для обычных криптовалют
        free_addr = db.session.query(cls.addr).filter(
            cls.crypto == crypto.crypto,
            cls.invoice_id == None  # Свободный адрес
        ).with_for_update(skip_locked=True).first()

        if free_addr:
            return free_addr[0]

        # Создаем новый
        new_addr = crypto.mkaddr(details={"value": amount_crypto} if amount_crypto else {})

        # Добавляем в пул
        new_address_record = cls()
        new_address_record.crypto = crypto.crypto
        new_address_record.addr = new_addr
        new_address_record.invoice_id = None
        db.session.add(new_address_record)
        db.session.flush()

        return new_addr

    @classmethod
    def assign_to_invoice(cls, addr, invoice_id):
        """
        Привязать адрес к инвойсу (пометить как занятый)
        """
        address_record = cls.query.filter_by(addr=addr, invoice_id=None).first()
        if address_record:
            address_record.invoice_id = invoice_id
            db.session.flush()

    @classmethod
    def release_address(cls, addr):
        """
        Освободить адрес (invoice_id = NULL)
        """
        address_records = cls.query.filter_by(addr=addr).filter(cls.invoice_id != None).all()
        for record in address_records:
            record.invoice_id = None
        db.session.flush()

    @classmethod
    def get_stats(cls, crypto_name):
        """
        Статистика по адресам
        """
        total = cls.query.filter_by(crypto=crypto_name).count()
        free = cls.query.filter_by(crypto=crypto_name, invoice_id=None).count()
        busy = total - free

        return {
            "crypto": crypto_name,
            "total_addresses": total,
            "free_addresses": free,
            "busy_addresses": busy
        }
```

---

### 3. Метод Invoice.add() - shkeeper/models.py:295-386

**Место 1 - Обновление существующего инвойса (строки 329-338):**

**Текущий код:**
```python
else:
    invoice.addr = crypto.mkaddr(
        details={"value": invoice.amount_crypto}
    )
    db.session.commit()
    invoice_address = InvoiceAddress()
    invoice_address.invoice_id = invoice.id
    invoice_address.crypto = invoice.crypto
    invoice_address.addr = invoice.addr
    db.session.add(invoice_address)
```

**Изменения:**
```python
else:
    # Получаем свободный адрес или создаем новый
    invoice.addr = InvoiceAddress.get_free_address(
        crypto,
        amount_crypto=invoice.amount_crypto
    )
    db.session.commit()

    # Привязываем адрес к инвойсу
    InvoiceAddress.assign_to_invoice(invoice.addr, invoice.id)
```

**Место 2 - Создание нового инвойса (строки 352-360):**

**Текущий код:**
```python
invoice.addr = crypto.mkaddr(details={"value": invoice.amount_crypto})
db.session.add(invoice)
db.session.commit()

invoice_address = InvoiceAddress()
invoice_address.invoice_id = invoice.id
invoice_address.crypto = invoice.crypto
invoice_address.addr = invoice.addr
db.session.add(invoice_address)
```

**Изменения:**
```python
# Получаем свободный адрес или создаем новый
invoice.addr = InvoiceAddress.get_free_address(
    crypto,
    amount_crypto=invoice.amount_crypto
)
db.session.add(invoice)
db.session.commit()

# Привязываем адрес к инвойсу
InvoiceAddress.assign_to_invoice(invoice.addr, invoice.id)
```

**Место 3 - Генерация BTC адреса для Lightning (строки 374-379):**

**Текущий код:**
```python
app.logger.debug("Generating a new on-chain BTC address")
btc_address = InvoiceAddress()
btc_address.crypto = "BTC"
btc_address.addr = btc.mkaddr()
btc_address.invoice_id = invoice.id
db.session.add(btc_address)
```

**Изменения:**
```python
app.logger.debug("Generating a new on-chain BTC address")
btc_addr = InvoiceAddress.get_free_address(btc, amount_crypto=None)
InvoiceAddress.assign_to_invoice(btc_addr, invoice.id)
```

---

### 4. Освобождение адреса при оплате - shkeeper/models.py:260-293

**Текущий код (метод update_with_tx, строки 288-290):**
```python
tx.invoice.status = InvoiceStatus.PAID
else:
    tx.invoice.status = InvoiceStatus.OVERPAID
```

**Изменения:**
```python
tx.invoice.status = InvoiceStatus.PAID
# Освобождаем адрес при оплате
InvoiceAddress.release_address(tx.invoice.addr)
else:
    tx.invoice.status = InvoiceStatus.OVERPAID
    # Освобождаем адрес при переплате
    InvoiceAddress.release_address(tx.invoice.addr)
```

---

### 5. Фоновая задача для освобождения истекших адресов

**Новый файл: shkeeper/tasks/cleanup_addresses.py**

```python
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
```

**Crontab запись:**
```bash
# Запускать каждый час
0 * * * * cd /home/shkeeper.io && python -m shkeeper.tasks.cleanup_addresses
```

---

### 6. Добавление индекса на поле addr в таблице Invoice

**Файл: shkeeper/models.py:214-237**

**Текущий код (строки 222, 237):**
```python
addr = db.Column(db.String)
...
)
```

**Изменения:**
```python
addr = db.Column(db.String, index=True)  # ДОБАВЛЕН: index=True
...
    __table_args__ = (
        db.Index('ix_invoice_addr', 'addr'),
    )
```

---

### 7. API метод для статистики

**Новый endpoint в shkeeper/api_v1.py (добавить после существующих endpoints):**

```python
@bp.get("/pool/stats")
@api_key_required
def get_pool_stats():
    """
    Получить статистику по пулу адресов для всех криптовалют

    Response:
    {
        "status": "success",
        "stats": {
            "BTC": {
                "crypto": "BTC",
                "total_addresses": 150,
                "free_addresses": 80,
                "busy_addresses": 70
            },
            ...
        }
    }
    """
    try:
        from shkeeper.modules.classes.crypto import Crypto

        stats = {}
        for crypto_name in Crypto.instances.keys():
            stats[crypto_name] = InvoiceAddress.get_stats(crypto_name)

        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        app.logger.exception("Failed to get pool statistics")
        return {
            "status": "error",
            "message": str(e)
        }


@bp.get("/pool/stats/<crypto_name>")
@api_key_required
def get_pool_stats_for_crypto(crypto_name):
    """
    Получить статистику по пулу адресов для конкретной криптовалюты

    Response:
    {
        "status": "success",
        "crypto": "BTC",
        "total_addresses": 150,
        "free_addresses": 80,
        "busy_addresses": 70
    }
    """
    try:
        stats = InvoiceAddress.get_stats(crypto_name)
        return {
            "status": "success",
            **stats
        }
    except Exception as e:
        app.logger.exception(f"Failed to get pool statistics for {crypto_name}")
        return {
            "status": "error",
            "message": str(e)
        }
```

---

## Миграция базы данных

**SQL для изменения существующей схемы:**

```sql
-- 1. Изменить invoice_address.invoice_id на nullable
ALTER TABLE invoice_address ALTER COLUMN invoice_id DROP NOT NULL;

-- 2. Добавить индексы на invoice_address
CREATE INDEX ix_invoice_address_crypto ON invoice_address(crypto);
CREATE INDEX ix_invoice_address_addr ON invoice_address(addr);
CREATE INDEX ix_invoice_address_crypto_invoice_id ON invoice_address(crypto, invoice_id);

-- 3. Добавить индекс на invoice.addr
CREATE INDEX ix_invoice_addr ON invoice(addr);

-- 4. Освободить все существующие адреса (опционально)
-- UPDATE invoice_address SET invoice_id = NULL;
```

---

## Итоговые изменения

### Файлы для изменения:

1. **shkeeper/models.py**:
   - Строка 222: добавить `index=True` для `Invoice.addr`
   - Строка 644: изменить `nullable=False` на `nullable=True` для `InvoiceAddress.invoice_id`
   - Строка 645-646: добавить `index=True` для `crypto` и `addr`
   - Строка 648: заменить `__table_args__` на новый с индексом
   - После строки 648: добавить методы `get_free_address()`, `assign_to_invoice()`, `release_address()`, `get_stats()`
   - Строка 330-338: заменить на новый код с `get_free_address()` и `assign_to_invoice()`
   - Строка 352-360: заменить на новый код с `get_free_address()` и `assign_to_invoice()`
   - Строка 377-379: заменить на новый код с `get_free_address()` и `assign_to_invoice()`
   - Строка 288-290: добавить `InvoiceAddress.release_address()` после установки статуса

2. **shkeeper/api_v1.py**:
   - Добавить два новых endpoint: `get_pool_stats()` и `get_pool_stats_for_crypto()`

3. **shkeeper/tasks/cleanup_addresses.py** (новый файл):
   - Создать фоновую задачу для освобождения истекших адресов

4. **Crontab**:
   - Добавить запись для запуска cleanup каждый час

5. **Миграция БД**:
   - Выполнить SQL команды для изменения схемы и добавления индексов
