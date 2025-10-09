#!/bin/bash
# Test extraction script

set -e

echo "=== SQL Extract Test Script ==="
echo ""

# Start SQL Server
echo "1. Starting SQL Server container..."
cd "$(dirname "$0")"
docker-compose up -d
echo "Waiting for SQL Server to be ready..."
sleep 30

# Create test database
echo ""
echo "2. Creating test database..."
docker exec sqlextract-test-db /opt/mssql-tools/bin/sqlcmd \
    -S localhost -U sa -P "Test@Password123!" \
    -Q "CREATE DATABASE SQLExtractTest"

# Load test schema
echo ""
echo "3. Loading test schema..."
docker exec -i sqlextract-test-db /opt/mssql-tools/bin/sqlcmd \
    -S localhost -U sa -P "Test@Password123!" -d SQLExtractTest \
    < tests/fixtures/test_schema.sql

# Run extraction
echo ""
echo "4. Running SQL Extract..."
python3 sqlextract.py \
    --server localhost \
    --database SQLExtractTest \
    --user sa \
    --password "Test@Password123!" \
    --trust-cert \
    --seed-data \
    --output ./test-output \
    --verbose

# Verify output files
echo ""
echo "5. Verifying output files..."
ls -lh test-output/

# Create verification database
echo ""
echo "6. Creating verification database..."
docker exec sqlextract-test-db /opt/mssql-tools/bin/sqlcmd \
    -S localhost -U sa -P "Test@Password123!" \
    -Q "CREATE DATABASE SQLExtractVerify"

# Deploy extracted schema
echo ""
echo "7. Deploying extracted schema..."
for file in test-output/*.sql; do
    echo "   Deploying $(basename $file)..."
    docker exec -i sqlextract-test-db /opt/mssql-tools/bin/sqlcmd \
        -S localhost -U sa -P "Test@Password123!" -d SQLExtractVerify \
        < "$file"
done

# Compare databases
echo ""
echo "8. Comparing databases..."
docker exec sqlextract-test-db /opt/mssql-tools/bin/sqlcmd \
    -S localhost -U sa -P "Test@Password123!" -d SQLExtractVerify \
    -Q "SELECT 'Tables:' AS Type, COUNT(*) AS Count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' UNION ALL SELECT 'Views:', COUNT(*) FROM INFORMATION_SCHEMA.VIEWS UNION ALL SELECT 'Procedures:', COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_TYPE = 'PROCEDURE'"

echo ""
echo "=== Test Complete! ==="
echo ""
echo "Output files are in: ./test-output/"
echo "To stop SQL Server: docker-compose down"
