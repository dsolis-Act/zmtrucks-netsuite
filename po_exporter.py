import json
import os
from collections import defaultdict
from datetime import datetime, UTC

from config import OUTPUT_FOLDER
from db import get_export_record, upsert_export_record


class PurchaseOrder943Exporter:
    EXPORT_TYPE = "purchase_order_943"
    business_unit = 'ZMTRUCKS'
    line_number = 0
    uom = "EA"

    def __init__(self, netsuite_client, logger):
        self.netsuite_client = netsuite_client
        self.logger = logger
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    def get_purchase_order_lines(self):
        query = """
            SELECT
                t.id,
                t.tranid,
                t.trandate,
                BUILTIN.DF(t.entity) AS vendor,
                BUILTIN.DF(t.status) AS status,
                BUILTIN.DF(t.custbodyzm_actlocation_field) AS act_location,
                t.custbodyzm_containernumber AS container_number,
                t.custbodyzm_sealnumber AS seal_number,
                BUILTIN.DF(t.location) AS header_location,
                t.transactionnumber,
                tl.item AS item_id,
                BUILTIN.DF(tl.item) AS item_name,
                tl.quantity AS qty,
                tl.rate AS rate,
                tl.amount AS amount,
                BUILTIN.DF(tl.location) AS line_location,
                BUILTIN.DF(tl.units) AS units,
                BUILTIN.DF(tl.department) AS department,
                BUILTIN.DF(tl.class) AS class_name,
                tl.memo AS line_memo
            FROM transaction t
            INNER JOIN transactionLine tl
                ON tl.transaction = t.id
            WHERE t.type = 'PurchOrd'
              AND t.custbodyzm_actlocation_field = 1
              AND tl.item IS NOT NULL
            ORDER BY t.trandate DESC, t.id DESC
        """
        return self.netsuite_client.run_suiteql(query)

    def group_purchase_orders(self, line_rows):
        grouped = defaultdict(list)

        for row in line_rows:
            grouped[str(row["id"])].append(row)

        return grouped

    def build_943_payload(self, header, line_rows):
        first_row = line_rows[0]

        ship_to_name = ""
        ship_to_address = ""
        ship_to_customer_id = ""

        if header.get("shipTo"):
            ship_to_name = header["shipTo"].get("refName", "")
            ship_to_customer_id = header["shipTo"].get("id", "")

        if header.get("shippingAddress_text"):
            ship_to_address = header["shippingAddress_text"].replace("<br>", ", ")
        elif header.get("shipAddress"):
            ship_to_address = header["shipAddress"].replace("<br>", ", ")

        # payload = {
        #     "Header": {
        #         "PurchaseOrderInternalId": first_row["id"],
        #         "PurchaseOrderNumber": first_row["tranid"],
        #         "TransactionNumber": first_row.get("transactionnumber", ""),
        #         "TransactionDate": first_row["trandate"],
        #         "Vendor": first_row["vendor"],
        #         "Status": first_row["status"],
        #         "ActLocation": first_row["act_location"],
        #         "HeaderLocation": first_row.get("header_location", ""),
        #         "ContainerNumber": first_row.get("container_number", ""),
        #         "SealNumber": first_row.get("seal_number", ""),
        #         "ShipToCustomerId": ship_to_customer_id,
        #         "ShipToName": ship_to_name,
        #         "ShipToAddress": ship_to_address,
        #         "ShipDate": header.get("shipDate", ""),
        #     },
        #     "LineItems": [],
        # }

        payload = {
            "Header": {
                "ShipmentHeader": {
                    "TradingPartnerId": "9WF3PLACTSOFTN",
                    "ShipmentIdentification": first_row.get("transactionnumber", ""),
                    "CurrentScheduledDeliveryDate": datetime.now().strftime("%Y-%m-%d")
                },
                "References": [
                    {
                        "ReferenceQual": "23",
                        "ReferenceID": f"9WFALL{self.business_unit}"
                    },
                    {
                        "ReferenceQual": "12",
                        "ReferenceID": self.business_unit,
                        "Description": self.business_unit
                    },
                    {
                        "ReferenceQual": "POID",
                        "ReferenceID": first_row.get("id", "")
                    }
                ],
                "Address": [
                    {
                        "AddressTypeCode": "ST",
                        "LocationCodeQualifier": "5201",
                        "AddressName": "PDC 1, Fontana, California",
                        "Country": "US"
                    },
                    {
                        "AddressTypeCode": "LF",
                        "AddressName": f"{self.business_unit} warehouse",
                        "Address1": "3155 Universe Dr",
                        "City": "Jurupa Valley",
                        "State": "CA",
                        "PostalCode": "91752",
                        "Country": "US"
                    },
                    {
                        "AddressTypeCode": "OSP",
                        "LocationCodeQualifier": "5201",
                        "AddressName": "PDC 1, Fontana, California",
                        "Country": "US"
                    }
                ],
                "QuantityAndWeight": [
                    {
                        "Weight": 0
                    }
                ]
            },
            "OrderLevel": [
                {
                    "OrderHeader": {
                        "PurchaseOrderNumber": first_row.get("container_number", "")
                    },
                    "ItemLevel": []
                }
            ]
        }

        # for row in line_rows:
        #     payload["LineItems"].append(
        #         {
        #             "ItemId": row["item_id"],
        #             "ItemName": row["item_name"],
        #             "Quantity": row["qty"],
        #             "Rate": row["rate"],
        #             "Amount": row["amount"],
        #             "LineLocation": row["line_location"],
        #             "Units": row["qty"],
        #             # "Department": row["department"],
        #             # "ClassName": row["class_name"],
        #             # "LineMemo": row["line_memo"],
        #         }
        #     )

        for index, row in enumerate(line_rows, start=1):
            self.line_number += index
            payload["OrderLevel"][0]["ItemLevel"].append(
                {
                "ShipmentLine": {
                    "LineSequenceNumber": self.line_number,
                    "BuyerPartNumber": row["item_name"],
                    "VendorPartNumber": row["item_name"],
                    "ConsumerPackageCode": row["item_name"],
                    "ShipQty": row["qty"],
                    "ShipQtyUOM": self.uom
                },
                "PhysicalDetails": [
                    {
                        "PackValue": 1
                    }
                ],
                "ProductOrItemDescription": [
                    {
                        "ProductDescription": ""
                    }
                ]    
                }
            )

        return payload

    def write_payload_file(self, po_number, payload):
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        file_name = f"AR_943_{po_number}_{timestamp}.json"
        file_path = os.path.join(OUTPUT_FOLDER, file_name)

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=1)

        return file_path

    def run(self):
        line_rows = self.get_purchase_order_lines()
        self.logger.info("Pulled %s SuiteQL line rows.", len(line_rows))

        grouped_purchase_orders = self.group_purchase_orders(line_rows)
        self.logger.info("Grouped into %s purchase orders.", len(grouped_purchase_orders))

        for po_internal_id, po_rows in grouped_purchase_orders.items():
            po_number = po_rows[0]["tranid"]
            suiteql_pulled_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            existing_export = get_export_record(self.EXPORT_TYPE, po_internal_id)

            if existing_export and existing_export["status"] == "success":
                self.logger.info("Skipping PO %s (%s). Already exported.", po_number, po_internal_id)
                continue

            try:
                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=po_internal_id,
                    record_number=po_number,
                    status="suiteql_pulled",
                    suiteql_pulled_at=suiteql_pulled_at,
                    error_message=None,
                )

                header = self.netsuite_client.get_purchase_order_header(po_internal_id)

                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=po_internal_id,
                    record_number=po_number,
                    status="header_pulled",
                    header_pulled_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    error_message=None,
                )

                payload = self.build_943_payload(header, po_rows)
                output_file = self.write_payload_file(po_number, payload)

                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=po_internal_id,
                    record_number=po_number,
                    status="success",
                    file_generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    output_file=output_file,
                    error_message=None,
                )

                self.logger.info("Successfully exported PO %s (%s) to %s", po_number, po_internal_id, output_file)

            except Exception as error:
                error_message = str(error)

                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=po_internal_id,
                    record_number=po_number,
                    status="failed",
                    error_message=error_message,
                )

                self.logger.exception("Failed exporting PO %s (%s): %s", po_number, po_internal_id, error_message)
                self.netsuite_client.send_failure_email(
                    subject=f"NetSuite 943 Export Failure - {po_number}",
                    body=(
                        f"Failed exporting purchase order.\n\n"
                        f"PO Number: {po_number}\n"
                        f"PO Internal ID: {po_internal_id}\n"
                        f"Error: {error_message}\n"
                    ),
                )
