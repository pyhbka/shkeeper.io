# Реализация привязки нескольких кошельков к одному инвойсу

## Цель
Добавить возможность привязывать несколько кошельков (по одному для каждой криптовалюты) к одному инвойсу через HTTP запросы.

---

## Изменения в файлах

### 1. shkeeper/models.py - Модификация Invoice.add()

**Файл:** `shkeeper/models.py`
**Строки:** 302-391

**Текущий код:**
```python
@classmethod
def add(cls, crypto, request):
    # {"external_id": "1234",  "fiat": "USD", "amount": 100.90, "callback_url": "https://blabla/callback.php"}
    crypto_is_lightning = "BTC-LIGHTNING" == crypto.crypto
    invoice = cls.query.filter_by(
        external_id=request["external_id"], callback_url=request["callback_url"]
    ).first()
    if invoice:
        # updating existing invoice
        invoice.fiat = request["fiat"]
        invoice.amount_fiat = Decimal(request["amount"])

        # recalc crypto amount for the new fiat amount
        rate = ExchangeRate.get(invoice.fiat, invoice.crypto)
        invoice.amount_crypto, invoice.exchange_rate = rate.convert(
            invoice.amount_fiat
        )

        crypto_changed = invoice.crypto != crypto.crypto
        if crypto_changed or crypto_is_lightning:
            invoice.crypto = crypto.crypto

            # recalc crypto amount for the new crypto and fiat amount
            rate = ExchangeRate.get(invoice.fiat, invoice.crypto)
            invoice.amount_crypto, invoice.exchange_rate = rate.convert(
                invoice.amount_fiat
            )

            # if address for new crypto already exist, use it instead of generating a new one
            invoice_address = InvoiceAddress.query.filter_by(
                invoice_id=invoice.id, crypto=crypto.crypto
            ).first()
            if invoice_address and not crypto_is_lightning:
                invoice.addr = invoice_address.addr
            else:
                # Получаем свободный адрес или создаем новый
                invoice.addr = InvoiceAddress.get_free_address(
                    crypto,
                    amount_crypto=invoice.amount_crypto
                )
                db.session.commit()

                # Привязываем адрес к инвойсу
                InvoiceAddress.assign_to_invoice(invoice.addr, invoice.id)

    else:
        # creating new invoice
        invoice = cls()
        invoice.crypto = crypto.crypto
        invoice.external_id = request["external_id"]
        invoice.callback_url = request["callback_url"]
        invoice.fiat = request["fiat"]
        invoice.amount_fiat = Decimal(request["amount"])
        rate = ExchangeRate.get(invoice.fiat, invoice.crypto)
        invoice.amount_crypto, invoice.exchange_rate = rate.convert(
            invoice.amount_fiat
        )
        # Получаем свободный адрес или создаем новый
        invoice.addr = InvoiceAddress.get_free_address(
            crypto,
            amount_crypto=invoice.amount_crypto
        )
        db.session.add(invoice)
        db.session.commit()

        # Привязываем адрес к инвойсу
        InvoiceAddress.assign_to_invoice(invoice.addr, invoice.id)

    if crypto_is_lightning and crypto.LIGHTNING_GENERATE_ONCHAIN_ADDRESS:
        app.logger.debug("Lightning requested on-chain address...")
        btc = Crypto.instances.get("BTC")

        if btc:
            btc_address = InvoiceAddress.query.filter_by(
                invoice_id=invoice.id, crypto="BTC"
            ).first()

            if btc_address:
                app.logger.debug("Using already existing on-chain BTC address")
            else:
                app.logger.debug("Generating a new on-chain BTC address")
                btc_addr = InvoiceAddress.get_free_address(btc, amount_crypto=None)
                InvoiceAddress.assign_to_invoice(btc_addr, invoice.id)
        else:
            raise Exception(
                "Lightning requested on-chain address generation but BTC wallet is not enabled in configuration"
            )

    db.session.commit()
    return invoice
```

**Новый код:**
```python
@classmethod
def add(cls, crypto, request, create_address=True):
    """
    Создать или обновить инвойс.

    Args:
        crypto: объект криптовалюты
        request: словарь с данными запроса
            {"external_id": "1234", "fiat": "USD", "amount": 100.90, "callback_url": "https://..."}
        create_address: если True - создать кошелек для указанной крипты,
                       если False - создать инвойс без кошелька
    """
    crypto_is_lightning = "BTC-LIGHTNING" == crypto.crypto
    invoice = cls.query.filter_by(
        external_id=request["external_id"], callback_url=request["callback_url"]
    ).first()
    if invoice:
        # updating existing invoice
        invoice.fiat = request["fiat"]
        invoice.amount_fiat = Decimal(request["amount"])

        # recalc crypto amount for the new fiat amount
        rate = ExchangeRate.get(invoice.fiat, invoice.crypto)
        invoice.amount_crypto, invoice.exchange_rate = rate.convert(
            invoice.amount_fiat
        )

        crypto_changed = invoice.crypto != crypto.crypto
        if crypto_changed or crypto_is_lightning:
            invoice.crypto = crypto.crypto

            # recalc crypto amount for the new crypto and fiat amount
            rate = ExchangeRate.get(invoice.fiat, invoice.crypto)
            invoice.amount_crypto, invoice.exchange_rate = rate.convert(
                invoice.amount_fiat
            )

            if create_address:
                # if address for new crypto already exist, use it instead of generating a new one
                invoice_address = InvoiceAddress.query.filter_by(
                    invoice_id=invoice.id, crypto=crypto.crypto
                ).first()
                if invoice_address and not crypto_is_lightning:
                    invoice.addr = invoice_address.addr
                else:
                    # Получаем свободный адрес или создаем новый
                    invoice.addr = InvoiceAddress.get_free_address(
                        crypto,
                        amount_crypto=invoice.amount_crypto
                    )
                    db.session.commit()

                    # Привязываем адрес к инвойсу
                    InvoiceAddress.assign_to_invoice(invoice.addr, invoice.id)

    else:
        # creating new invoice
        invoice = cls()
        invoice.crypto = crypto.crypto
        invoice.external_id = request["external_id"]
        invoice.callback_url = request["callback_url"]
        invoice.fiat = request["fiat"]
        invoice.amount_fiat = Decimal(request["amount"])
        rate = ExchangeRate.get(invoice.fiat, invoice.crypto)
        invoice.amount_crypto, invoice.exchange_rate = rate.convert(
            invoice.amount_fiat
        )

        if create_address:
            # Получаем свободный адрес или создаем новый
            invoice.addr = InvoiceAddress.get_free_address(
                crypto,
                amount_crypto=invoice.amount_crypto
            )

        db.session.add(invoice)
        db.session.commit()

        if create_address:
            # Привязываем адрес к инвойсу
            InvoiceAddress.assign_to_invoice(invoice.addr, invoice.id)

    if create_address and crypto_is_lightning and crypto.LIGHTNING_GENERATE_ONCHAIN_ADDRESS:
        app.logger.debug("Lightning requested on-chain address...")
        btc = Crypto.instances.get("BTC")

        if btc:
            btc_address = InvoiceAddress.query.filter_by(
                invoice_id=invoice.id, crypto="BTC"
            ).first()

            if btc_address:
                app.logger.debug("Using already existing on-chain BTC address")
            else:
                app.logger.debug("Generating a new on-chain BTC address")
                btc_addr = InvoiceAddress.get_free_address(btc, amount_crypto=None)
                InvoiceAddress.assign_to_invoice(btc_addr, invoice.id)
        else:
            raise Exception(
                "Lightning requested on-chain address generation but BTC wallet is not enabled in configuration"
            )

    db.session.commit()
    return invoice
```

---

### 2. shkeeper/api_v1.py - Добавление новых endpoints

**Файл:** `shkeeper/api_v1.py`
**Место:** после строки 775 (после `test_callback_receiver`)

**Новый код для добавления:**

```python
@bp.post("/<crypto_name>/invoice/<int:invoice_id>/get_address")
@api_key_required
def get_address_for_invoice(crypto_name, invoice_id):
    """
    Привязать адрес криптовалюты к существующему инвойсу.
    Если адрес для данной крипты уже существует - вернуть его.

    Response:
    {
        "status": "success",
        "invoice_id": 123,
        "crypto": "BTC",
        "address": "bc1q...",
        "amount_crypto": "0.00123456",
        "exchange_rate": "45000.00"
    }
    """
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

        # Найти инвойс
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return {
                "status": "error",
                "message": f"Invoice {invoice_id} not found",
            }

        # Проверить, есть ли уже адрес этой крипты для инвойса
        existing_address = InvoiceAddress.query.filter_by(
            invoice_id=invoice.id,
            crypto=crypto_name
        ).first()

        if existing_address:
            # Рассчитать сумму в крипте
            rate = ExchangeRate.get(invoice.fiat, crypto_name)
            amount_crypto, exchange_rate = rate.convert(invoice.amount_fiat)

            return {
                "status": "success",
                "invoice_id": invoice.id,
                "crypto": crypto_name,
                "address": existing_address.addr,
                "amount_crypto": format_decimal(amount_crypto),
                "exchange_rate": format_decimal(exchange_rate, 2),
            }

        # Рассчитать сумму в крипте
        rate = ExchangeRate.get(invoice.fiat, crypto_name)
        amount_crypto, exchange_rate = rate.convert(invoice.amount_fiat)

        # Получить свободный адрес или создать новый
        addr = InvoiceAddress.get_free_address(crypto, amount_crypto=amount_crypto)
        InvoiceAddress.assign_to_invoice(addr, invoice.id)
        db.session.commit()

        app.logger.info(f"Assigned {crypto_name} address {addr} to invoice {invoice_id}")

        return {
            "status": "success",
            "invoice_id": invoice.id,
            "crypto": crypto_name,
            "address": addr,
            "amount_crypto": format_decimal(amount_crypto),
            "exchange_rate": format_decimal(exchange_rate, 2),
        }

    except Exception as e:
        app.logger.exception(f"Failed to get address for invoice {invoice_id}, crypto {crypto_name}")
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
        }


@bp.get("/invoice/<int:invoice_id>/addresses")
@api_key_required
def get_invoice_addresses(invoice_id):
    """
    Получить все адреса, привязанные к инвойсу.

    Response:
    {
        "status": "success",
        "invoice_id": 123,
        "addresses": [
            {
                "crypto": "BTC",
                "address": "bc1q...",
                "amount_crypto": "0.00123456",
                "exchange_rate": "45000.00"
            },
            {
                "crypto": "ETH",
                "address": "0x...",
                "amount_crypto": "0.05",
                "exchange_rate": "3000.00"
            }
        ]
    }
    """
    try:
        # Найти инвойс
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return {
                "status": "error",
                "message": f"Invoice {invoice_id} not found",
            }

        # Получить все адреса инвойса
        invoice_addresses = InvoiceAddress.query.filter_by(invoice_id=invoice.id).all()

        addresses = []
        for ia in invoice_addresses:
            try:
                rate = ExchangeRate.get(invoice.fiat, ia.crypto)
                amount_crypto, exchange_rate = rate.convert(invoice.amount_fiat)
                addresses.append({
                    "crypto": ia.crypto,
                    "address": ia.addr,
                    "amount_crypto": format_decimal(amount_crypto),
                    "exchange_rate": format_decimal(exchange_rate, 2),
                })
            except Exception as e:
                # Если курс недоступен, вернуть адрес без суммы
                addresses.append({
                    "crypto": ia.crypto,
                    "address": ia.addr,
                    "amount_crypto": None,
                    "exchange_rate": None,
                    "error": str(e),
                })

        return {
            "status": "success",
            "invoice_id": invoice.id,
            "external_id": invoice.external_id,
            "fiat": invoice.fiat,
            "amount_fiat": format_decimal(invoice.amount_fiat),
            "addresses": addresses,
        }

    except Exception as e:
        app.logger.exception(f"Failed to get addresses for invoice {invoice_id}")
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
        }
```

---

## Итоговый список изменений

### Файлы для изменения:

| Файл | Строки | Тип изменения | Описание |
|------|--------|---------------|----------|
| `shkeeper/models.py` | 302-391 | Модификация | Добавить параметр `create_address=True` в метод `Invoice.add()` |
| `shkeeper/api_v1.py` | после 775 | Добавление | Добавить endpoint `POST /<crypto_name>/invoice/<invoice_id>/get_address` |
| `shkeeper/api_v1.py` | после 775 | Добавление | Добавить endpoint `GET /invoice/<invoice_id>/addresses` |

---

## Использование API

### 1. Создание инвойса без кошелька

Для создания инвойса без кошелька нужно модифицировать вызов в `api_v1.py:payment_request`:

```python
# Текущий вызов (создает инвойс с кошельком):
invoice = Invoice.add(crypto=crypto, request=req)

# Для создания без кошелька (если в request есть флаг):
create_address = req.get("create_address", True)
invoice = Invoice.add(crypto=crypto, request=req, create_address=create_address)
```

### 2. Привязка адреса к существующему инвойсу

**Запрос:**
```
POST /api/v1/BTC/invoice/123/get_address
Headers:
  X-Shkeeper-API-Key: <api_key>
```

**Ответ:**
```json
{
    "status": "success",
    "invoice_id": 123,
    "crypto": "BTC",
    "address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
    "amount_crypto": "0.00123456",
    "exchange_rate": "45000.00"
}
```

### 3. Получение всех адресов инвойса

**Запрос:**
```
GET /api/v1/invoice/123/addresses
Headers:
  X-Shkeeper-API-Key: <api_key>
```

**Ответ:**
```json
{
    "status": "success",
    "invoice_id": 123,
    "external_id": "order_456",
    "fiat": "USD",
    "amount_fiat": "100.00",
    "addresses": [
        {
            "crypto": "BTC",
            "address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
            "amount_crypto": "0.00222222",
            "exchange_rate": "45000.00"
        },
        {
            "crypto": "ETH",
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f9bB7a",
            "amount_crypto": "0.03333333",
            "exchange_rate": "3000.00"
        },
        {
            "crypto": "USDT-TRC20",
            "address": "TJYvqBcXtMpqCzP3rM5Xm9mEfz8k2gJp9a",
            "amount_crypto": "100.00000000",
            "exchange_rate": "1.00"
        }
    ]
}
```

---

## Порядок внесения изменений

1. **Сначала** изменить `shkeeper/models.py`:
   - Добавить параметр `create_address=True` в сигнатуру метода `Invoice.add()`
   - Обернуть логику создания адреса в условие `if create_address:`

2. **Затем** добавить новые endpoints в `shkeeper/api_v1.py`:
   - `POST /<crypto_name>/invoice/<invoice_id>/get_address`
   - `GET /invoice/<invoice_id>/addresses`

3. **Опционально** модифицировать `payment_request` endpoint для поддержки флага `create_address` в запросе.
