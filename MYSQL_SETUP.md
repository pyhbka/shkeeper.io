# MySQL Setup Guide for SHKeeper

This guide explains how to set up and configure SHKeeper with MySQL database.

## Prerequisites

- MySQL 5.7+ or MariaDB 10.3+
- Python 3.8+
- Access to MySQL server with CREATE DATABASE privileges

## Database Setup

### 1. Create MySQL Database and User

Connect to your MySQL server and run:

```sql
-- Create database
CREATE DATABASE shkeeper CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (replace 'your_password' with a strong password)
CREATE USER 'shkeeper'@'localhost' IDENTIFIED BY 'your_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON shkeeper.* TO 'shkeeper'@'localhost';
FLUSH PRIVILEGES;
```

For remote access, replace `'localhost'` with `'%'` or specific IP address.

### 2. Configure Environment Variables

SHKeeper reads MySQL connection settings from environment variables:

```bash
export MYSQL_HOST=localhost        # MySQL server host
export MYSQL_PORT=3306             # MySQL server port
export MYSQL_USER=shkeeper         # MySQL username
export MYSQL_PASSWORD=your_password # MySQL password
export MYSQL_DATABASE=shkeeper     # MySQL database name
```

**For production, use a secure method to store credentials:**
- Docker Secrets
- Kubernetes Secrets
- HashiCorp Vault
- AWS Secrets Manager
- Environment-specific configuration files

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `pymysql>=1.0.2` - MySQL driver
- `cryptography>=3.4.8` - Required by pymysql
- All other SHKeeper dependencies

### 4. Initialize Database

Run Alembic migrations to create tables:

```bash
# From the project root directory
flask db upgrade
```

Or if using Python module:

```bash
python -m flask db upgrade
```

### 5. Verify Installation

Check database connection:

```bash
mysql -u shkeeper -p shkeeper -e "SHOW TABLES;"
```

You should see tables like:
- `user`
- `wallet`
- `invoice`
- `transaction`
- `exchange_rate`
- etc.

## Docker Setup

### Using Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: shkeeper
      MYSQL_USER: shkeeper
      MYSQL_PASSWORD: shkeeper_password
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  shkeeper:
    build: .
    environment:
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
      MYSQL_USER: shkeeper
      MYSQL_PASSWORD: shkeeper_password
      MYSQL_DATABASE: shkeeper
    ports:
      - "5000:5000"
    depends_on:
      mysql:
        condition: service_healthy

volumes:
  mysql_data:
```

Run:

```bash
docker-compose up -d
```

### Using Docker with External MySQL

```bash
docker build -t shkeeper .

docker run -d \
  --name shkeeper \
  -p 5000:5000 \
  -e MYSQL_HOST=your_mysql_host \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=shkeeper \
  -e MYSQL_PASSWORD=your_password \
  -e MYSQL_DATABASE=shkeeper \
  shkeeper
```

## Kubernetes Setup

Create `mysql-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: shkeeper-mysql-secret
type: Opaque
stringData:
  MYSQL_HOST: mysql-service
  MYSQL_PORT: "3306"
  MYSQL_USER: shkeeper
  MYSQL_PASSWORD: your_secure_password
  MYSQL_DATABASE: shkeeper
```

Create `shkeeper-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shkeeper
spec:
  replicas: 3
  selector:
    matchLabels:
      app: shkeeper
  template:
    metadata:
      labels:
        app: shkeeper
    spec:
      containers:
      - name: shkeeper
        image: shkeeper:latest
        ports:
        - containerPort: 5000
        envFrom:
        - secretRef:
            name: shkeeper-mysql-secret
```

Apply:

```bash
kubectl apply -f mysql-secret.yaml
kubectl apply -f shkeeper-deployment.yaml
```

## Password Management

### Setting Initial Admin Password

On first run, SHKeeper will prompt you to set an admin password via the web interface at `/set-password`.

### Changing Admin Password

Use the provided script:

```bash
# Set environment variables
export MYSQL_HOST=localhost
export MYSQL_USER=shkeeper
export MYSQL_PASSWORD=your_password
export MYSQL_DATABASE=shkeeper

# Run the script
python3 contrib/shkeeper-change-password.py
```

## Connection Pool Configuration

The application uses connection pooling with these default settings:

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,           # Number of connections to keep open
    'pool_recycle': 3600,      # Recycle connections after 1 hour
    'pool_pre_ping': True,     # Check connection health before using
}
```

To adjust these, modify `shkeeper/__init__.py` in the `create_app()` function.

## MySQL Configuration Recommendations

### For Production

Add to your MySQL configuration (`/etc/mysql/my.cnf` or similar):

```ini
[mysqld]
# Character set
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

# Connection limits
max_connections = 200
max_allowed_packet = 64M

# InnoDB settings
innodb_buffer_pool_size = 1G
innodb_log_file_size = 256M
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT

# Query cache (MySQL 5.7 and earlier)
query_cache_type = 1
query_cache_size = 64M

# Logging
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow-query.log
long_query_time = 2
```

### Restart MySQL after configuration changes:

```bash
sudo systemctl restart mysql
```

## Backup and Restore

### Backup

```bash
mysqldump -u shkeeper -p \
  --single-transaction \
  --routines \
  --triggers \
  shkeeper > shkeeper_backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore

```bash
mysql -u shkeeper -p shkeeper < shkeeper_backup_20241203_120000.sql
```

### Automated Backups

Create a cron job (`crontab -e`):

```bash
# Daily backup at 2 AM
0 2 * * * /usr/bin/mysqldump -u shkeeper -pYOUR_PASSWORD --single-transaction shkeeper > /backups/shkeeper_$(date +\%Y\%m\%d).sql
```

## Monitoring

### Check Database Connection

```bash
mysql -u shkeeper -p -e "SELECT 1;"
```

### Monitor Active Connections

```sql
SHOW PROCESSLIST;
```

### Check Table Sizes

```sql
SELECT
    table_name AS 'Table',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.TABLES
WHERE table_schema = 'shkeeper'
ORDER BY (data_length + index_length) DESC;
```

## Troubleshooting

### Connection Refused

```
Error: Can't connect to MySQL server on 'localhost'
```

**Solution:**
- Check MySQL is running: `sudo systemctl status mysql`
- Verify firewall allows port 3306
- Check `MYSQL_HOST` is correct

### Access Denied

```
Error: Access denied for user 'shkeeper'@'localhost'
```

**Solution:**
- Verify credentials are correct
- Check user has proper privileges:
  ```sql
  SHOW GRANTS FOR 'shkeeper'@'localhost';
  ```

### Character Set Issues

```
Error: Incorrect string value
```

**Solution:**
- Ensure database uses utf8mb4:
  ```sql
  ALTER DATABASE shkeeper CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  ```

### Too Many Connections

```
Error: Too many connections
```

**Solution:**
- Increase `max_connections` in MySQL config
- Check for connection leaks in application
- Adjust connection pool size

## Security Best Practices

1. **Use strong passwords** - Minimum 16 characters with mixed case, numbers, and symbols
2. **Limit network access** - Use firewall rules to restrict MySQL port
3. **Use SSL/TLS** - Enable encrypted connections:
   ```python
   mysql_uri = f"mysql+pymysql://{user}:{password}@{host}/{db}?ssl_ca=/path/to/ca.pem"
   ```
4. **Regular updates** - Keep MySQL and pymysql up to date
5. **Backup encryption** - Encrypt backup files
6. **Audit logging** - Enable MySQL audit plugin
7. **Principle of least privilege** - Grant only required permissions

## Migration from SQLite

If you have an existing SQLite database and want to migrate to MySQL:

### Option 1: Using mysql-connector-python

```bash
# Install converter
pip install mysql-connector-python

# Convert (example script needed)
python convert_sqlite_to_mysql.py
```

### Option 2: Manual Migration

1. Export data from SQLite
2. Create fresh MySQL database
3. Run migrations: `flask db upgrade`
4. Import data using SQL scripts

**Note:** This is a complex process. Consider starting fresh with MySQL if possible.

## Performance Tuning

### Index Optimization

Check for missing indexes:

```sql
SELECT * FROM sys.schema_unused_indexes;
```

### Query Analysis

Enable slow query log and analyze:

```sql
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
```

### Connection Pool Tuning

Monitor connection usage and adjust pool settings accordingly.

## Support

For issues specific to MySQL setup:
- Check application logs
- Review MySQL error log: `/var/log/mysql/error.log`
- Open an issue on GitHub with detailed error messages

## Additional Resources

- [MySQL Documentation](https://dev.mysql.com/doc/)
- [SQLAlchemy MySQL Dialect](https://docs.sqlalchemy.org/en/14/dialects/mysql.html)
- [pymysql Documentation](https://pymysql.readthedocs.io/)
