/*
 * Test Database Schema for SQL Extract
 * This schema tests various SQL Server features
 */

SET QUOTED_IDENTIFIER ON
GO
SET ANSI_NULLS ON
GO

-- Create schemas
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'MQTT')
    EXEC('CREATE SCHEMA MQTT')
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'Logging')
    EXEC('CREATE SCHEMA Logging')
GO

-- Create tables with various features
CREATE TABLE dbo.Config (
    ConfigID INT IDENTITY(1,1) NOT NULL,
    ConfigKey NVARCHAR(100) NOT NULL,
    ConfigValue NVARCHAR(MAX) NULL,
    IsEnabled BIT NOT NULL DEFAULT 1,
    CreatedDate DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT PK_Config PRIMARY KEY CLUSTERED (ConfigID),
    CONSTRAINT UQ_Config_Key UNIQUE (ConfigKey),
    CONSTRAINT CK_Config_Key CHECK (LEN(ConfigKey) > 0)
)
GO

CREATE TABLE MQTT.Broker (
    BrokerID INT IDENTITY(1,1) NOT NULL,
    BrokerName NVARCHAR(100) NOT NULL,
    HostName NVARCHAR(255) NOT NULL,
    Port INT NOT NULL DEFAULT 1883,
    IsSecure BIT NOT NULL DEFAULT 0,
    CreatedDate DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT PK_Broker PRIMARY KEY CLUSTERED (BrokerID)
)
GO

CREATE TABLE MQTT.ReceiverConfig (
    ReceiverConfigID INT IDENTITY(1,1) NOT NULL,
    BrokerID INT NOT NULL,
    Topic NVARCHAR(255) NOT NULL,
    QoS TINYINT NOT NULL DEFAULT 0,
    IsEnabled BIT NOT NULL DEFAULT 1,
    RetryCount INT NOT NULL DEFAULT 3,
    CreatedDate DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
    ModifiedDate DATETIME2(3) NULL,
    CONSTRAINT PK_ReceiverConfig PRIMARY KEY CLUSTERED (ReceiverConfigID),
    CONSTRAINT FK_ReceiverConfig_Broker FOREIGN KEY (BrokerID) REFERENCES MQTT.Broker(BrokerID) ON DELETE CASCADE,
    CONSTRAINT CK_ReceiverConfig_QoS CHECK (QoS BETWEEN 0 AND 2),
    CONSTRAINT CK_ReceiverConfig_RetryCount CHECK (RetryCount >= 0)
)
GO

CREATE TABLE Logging.EventLog (
    EventID BIGINT IDENTITY(1,1) NOT NULL,
    EventType NVARCHAR(50) NOT NULL,
    Message NVARCHAR(MAX) NOT NULL,
    Severity TINYINT NOT NULL DEFAULT 1,
    CreatedDate DATETIME2(7) NOT NULL DEFAULT SYSDATETIME(),
    EventData NVARCHAR(MAX) NULL,
    CONSTRAINT PK_EventLog PRIMARY KEY CLUSTERED (EventID)
)
GO

CREATE TABLE Logging.ErrorLog (
    ErrorID BIGINT IDENTITY(1,1) NOT NULL,
    ErrorMessage NVARCHAR(MAX) NOT NULL,
    StackTrace NVARCHAR(MAX) NULL,
    Source NVARCHAR(255) NULL,
    CreatedDate DATETIME2(7) NOT NULL DEFAULT SYSDATETIME(),
    CONSTRAINT PK_ErrorLog PRIMARY KEY CLUSTERED (ErrorID)
)
GO

-- Table with computed column
CREATE TABLE dbo.Orders (
    OrderID INT IDENTITY(1,1) NOT NULL,
    CustomerName NVARCHAR(100) NOT NULL,
    OrderDate DATETIME2(3) NOT NULL DEFAULT GETUTCDATE(),
    SubTotal DECIMAL(18,2) NOT NULL,
    TaxRate DECIMAL(5,4) NOT NULL DEFAULT 0.0825,
    TaxAmount AS (SubTotal * TaxRate) PERSISTED,
    TotalAmount AS (SubTotal * (1 + TaxRate)),
    CONSTRAINT PK_Orders PRIMARY KEY CLUSTERED (OrderID)
)
GO

-- Create indexes
CREATE NONCLUSTERED INDEX IX_ReceiverConfig_BrokerID
ON MQTT.ReceiverConfig(BrokerID)
GO

CREATE NONCLUSTERED INDEX IX_ReceiverConfig_Topic
ON MQTT.ReceiverConfig(Topic)
WHERE IsEnabled = 1
GO

CREATE NONCLUSTERED INDEX IX_EventLog_EventType_CreatedDate
ON Logging.EventLog(EventType, CreatedDate DESC)
INCLUDE (Message, Severity)
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_Broker_HostName_Port
ON MQTT.Broker(HostName, Port)
GO

-- Create view
CREATE VIEW MQTT.vwActiveReceivers
AS
SELECT
    rc.ReceiverConfigID,
    rc.Topic,
    rc.QoS,
    b.BrokerName,
    b.HostName,
    b.Port,
    rc.CreatedDate
FROM MQTT.ReceiverConfig rc
INNER JOIN MQTT.Broker b ON rc.BrokerID = b.BrokerID
WHERE rc.IsEnabled = 1
GO

-- Create stored procedure
CREATE PROCEDURE MQTT.sp_GetReceiversByBroker
    @BrokerID INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        ReceiverConfigID,
        Topic,
        QoS,
        IsEnabled,
        CreatedDate
    FROM MQTT.ReceiverConfig
    WHERE BrokerID = @BrokerID
    ORDER BY Topic
END
GO

-- Create function
CREATE FUNCTION dbo.fn_GetConfigValue
(
    @ConfigKey NVARCHAR(100)
)
RETURNS NVARCHAR(MAX)
AS
BEGIN
    DECLARE @Value NVARCHAR(MAX)

    SELECT @Value = ConfigValue
    FROM dbo.Config
    WHERE ConfigKey = @ConfigKey
      AND IsEnabled = 1

    RETURN @Value
END
GO

-- Create table-valued function
CREATE FUNCTION Logging.fn_GetRecentEvents
(
    @Hours INT = 24
)
RETURNS TABLE
AS
RETURN
(
    SELECT
        EventID,
        EventType,
        Message,
        Severity,
        CreatedDate
    FROM Logging.EventLog
    WHERE CreatedDate >= DATEADD(HOUR, -@Hours, SYSDATETIME())
)
GO

-- Insert seed data
SET IDENTITY_INSERT dbo.Config ON
INSERT INTO dbo.Config (ConfigID, ConfigKey, ConfigValue, IsEnabled, CreatedDate)
VALUES
    (1, 'AppName', 'SQL Extract Test', 1, '2025-01-01 00:00:00'),
    (2, 'Version', '1.0.0', 1, '2025-01-01 00:00:00'),
    (3, 'MaxRetries', '3', 1, '2025-01-01 00:00:00'),
    (4, 'Timeout', '30', 1, '2025-01-01 00:00:00'),
    (5, 'DebugMode', 'false', 0, '2025-01-01 00:00:00')
SET IDENTITY_INSERT dbo.Config OFF
GO

SET IDENTITY_INSERT MQTT.Broker ON
INSERT INTO MQTT.Broker (BrokerID, BrokerName, HostName, Port, IsSecure, CreatedDate)
VALUES
    (1, 'Local MQTT', 'localhost', 1883, 0, '2025-01-01 00:00:00'),
    (2, 'Cloud MQTT', 'mqtt.cloud.com', 8883, 1, '2025-01-01 00:00:00'),
    (3, 'Edge MQTT', '192.168.1.100', 1883, 0, '2025-01-01 00:00:00')
SET IDENTITY_INSERT MQTT.Broker OFF
GO

SET IDENTITY_INSERT MQTT.ReceiverConfig ON
INSERT INTO MQTT.ReceiverConfig (ReceiverConfigID, BrokerID, Topic, QoS, IsEnabled, RetryCount, CreatedDate)
VALUES
    (1, 1, 'sensors/temperature', 0, 1, 3, '2025-01-01 00:00:00'),
    (2, 1, 'sensors/humidity', 0, 1, 3, '2025-01-01 00:00:00'),
    (3, 2, 'devices/+/status', 1, 1, 5, '2025-01-01 00:00:00'),
    (4, 3, 'alerts/#', 2, 1, 5, '2025-01-01 00:00:00'),
    (5, 2, 'test/disabled', 0, 0, 3, '2025-01-01 00:00:00')
SET IDENTITY_INSERT MQTT.ReceiverConfig OFF
GO

SET IDENTITY_INSERT Logging.EventLog ON
INSERT INTO Logging.EventLog (EventID, EventType, Message, Severity, CreatedDate)
VALUES
    (1, 'INFO', 'Application started', 1, '2025-01-01 08:00:00'),
    (2, 'INFO', 'Database connected', 1, '2025-01-01 08:00:01'),
    (3, 'WARNING', 'High memory usage detected', 2, '2025-01-01 09:15:30'),
    (4, 'ERROR', 'Failed to connect to MQTT broker', 3, '2025-01-01 10:30:45'),
    (5, 'INFO', 'Cleanup task completed', 1, '2025-01-01 11:00:00')
SET IDENTITY_INSERT Logging.EventLog OFF
GO

SET IDENTITY_INSERT dbo.Orders ON
INSERT INTO dbo.Orders (OrderID, CustomerName, OrderDate, SubTotal, TaxRate)
VALUES
    (1, 'John Doe', '2025-01-01', 100.00, 0.0825),
    (2, 'Jane Smith', '2025-01-02', 250.50, 0.0825),
    (3, 'Bob Johnson', '2025-01-03', 75.25, 0.0825)
SET IDENTITY_INSERT dbo.Orders OFF
GO

PRINT 'Test database schema created successfully!'
GO
