from db import initialize_database
from logger_setup import get_logger
from netsuite_client import NetSuiteClient
from po_exporter import PurchaseOrder943Exporter
from so_exporter import SalesOrderExporter


def main():
    initialize_database()

    logger = get_logger()
    netsuite_client = NetSuiteClient(logger)
    po_exporter = PurchaseOrder943Exporter(netsuite_client, logger)
    po_exporter.run()
    so_export = SalesOrderExporter(netsuite_client, logger)
    so_export.run()


if __name__ == "__main__":
    main()
