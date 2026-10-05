import json
import os
from collections import defaultdict
from datetime import datetime, UTC

from config import OUTPUT_FOLDER
from db import get_export_record, upsert_export_record


class SalesOrderExporter:
    EXPORT_TYPE = "sales_order_940"
    business_unit = "ZMTRUCKS"
    customer_account_number = "ZMTRUCK"
    uom = "EA"

    def __init__(self, netsuite_client, logger):
        self.netsuite_client = netsuite_client
        self.logger = logger
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    def get_sales_order_lines(self):
        query = """
            SELECT
                t.id,
                t.tranid,
                t.trandate,
                BUILTIN.DF(t.entity) AS customer,
                BUILTIN.DF(t.status) AS status,
                BUILTIN.DF(t.custbodyzm_actlocation_field) AS act_location,
                BUILTIN.DF(t.custbodyzm_scac) AS scac,
                BUILTIN.DF(t.custbodyzm_servicetype) AS service_type,
                t.transactionnumber,
                tl.item AS item_id,
                BUILTIN.DF(tl.item) AS item_name,
                tl.custcolzm_vinnumber_line AS vin,
                tl.quantity AS qty,
                tl.amount AS amount
            FROM transaction t
            INNER JOIN transactionLine tl
                ON tl.transaction = t.id
            WHERE t.type = 'SalesOrd'
              AND t.custbodyzm_actlocation_field = 1
              AND tl.item IS NOT NULL
              AND tl.item <> -7
              AND tl.quantity <> 0
            ORDER BY t.trandate DESC, t.id DESC
        """
        return self.netsuite_client.run_suiteql(query)




    def group_sales_orders(self, line_rows):
        grouped = defaultdict(list)

        for row in line_rows:
            grouped[str(row["id"])].append(row)

        return grouped

    def build_940_payload(self, header, line_rows):
        first_row = line_rows[0]
        so_id = first_row.get("id", "")
        order_number = first_row.get("tranid", "")
        tran_date = header.get("tranDate", "") or first_row.get("trandate", "")
        ship_date = header.get("shipDate", "") or tran_date

        ship_to_name = ""
        ship_to_address_1 = ""
        ship_to_city = ""
        ship_to_state = ""
        ship_to_postal_code = ""
        ship_to_country = "US"

        if header.get("entity"):
            ship_to_name = header["entity"].get("refName", "")

        if header.get("shippingAddress"):
            shipping_address = header["shippingAddress"]
            ship_to_country = shipping_address.get("country", {}).get("id", "US") or "US"

            # use full structured fields if they ever show up
            ship_to_address_1 = shipping_address.get("addr1", "") or shipping_address.get("addrText", "")
            ship_to_city = shipping_address.get("city", "")
            ship_to_state = shipping_address.get("state", "")
            ship_to_postal_code = shipping_address.get("zip", "")

        # adding logic to not pull in flatbed as an item 06/29 DS
        ship_method_id = ""
        if header.get("shipMethod"):
            ship_method_id = str(header["shipMethod"].get("id", ""))

        payload = {
            "Header": {
                "OrderHeader": {
                    "TradingPartnerId": "9WF3PLACTSOFTN",
                    "PurchaseOrderNumber": order_number,
                    "DepositorOrderNumber": order_number,
                    "CustomerAccountNumber": self.customer_account_number,
                    "CustomerOrderNumber": order_number
                },
                "Dates": [
                    {
                        "DateTimeQualifier": "006",
                        "Date": ship_date
                    },
                    {
                        "DateTimeQualifier": "003",
                        "Date": tran_date
                    },
                    {
                        "DateTimeQualifier": "001",
                        "Date": tran_date
                    },
                    {
                        "DateTimeQualifier": "007",
                        "Date": ship_date
                    },
                    {
                        "DateTimeQualifier": "010",
                        "Date": ship_date
                    },
                    {
                        "DateTimeQualifier": "015",
                        "Date": ship_date
                    }
                ],
                "Address": [
                    {
                        "AddressTypeCode": "SF",
                        "LocationCodeQualifier": "5201",
                        "AddressName": "PDC 1, Fontana, California",
                        "Country": "US"
                    },
                    {
                        "AddressTypeCode": "ST",
                        "AddressName": ship_to_name,
                        "Address1": ship_to_address_1,
                        "City": ship_to_city,
                        "State": ship_to_state,
                        "PostalCode": ship_to_postal_code,
                        "Country": ship_to_country
                    }
                ],
                "FOBRelatedInstruction": [
                    {
                        "FOBPayCode": "TP"
                    }
                ],
                "CarrierInformation": [
                    {
                        "CarrierTransMethodCode": "M",
                        "CarrierAlphaCode": first_row.get("scac", ""),
                        "CarrierRouting": first_row.get("service_type", ""),
                        "ServiceLevelCodes": [
                            {
                                "ServiceLevelCode": first_row.get("service_type", "")
                            }
                        ]
                    }
                ],
                "References": [
                    {
                        "ReferenceQual": "23",
                        "ReferenceID": self.business_unit
                    },
                    {
                        "ReferenceQual": "12",
                        "ReferenceID": self.business_unit,
                        "Description": self.business_unit
                    },
                    {
                        "ReferenceQual": "ACT",
                        "ReferenceID": f"DF{self.business_unit}",
                        "Description": ""
                    },
                    {
                        "ReferenceQual": "SOID",
                        "ReferenceID": so_id,
                    }
                ]
            },
            "LineItem": []
        }

        for index, row in enumerate(line_rows, start=1):
            # adding logic to not pull in flatbed as an item 06/29 DS
            if str(row.get("item_id")) == "-7":
                continue

            if ship_method_id and str(row.get("item_id")) == ship_method_id:
                continue


            payload["LineItem"].append(
                {
                    "OrderLine": {
                        "LineSequenceNumber": f"{index}",
                        "VendorPartNumber": row.get("item_name", ""),
                        "ConsumerPackageCode": row.get("item_name", ""),
                        "OrderQty": abs(float(row.get("qty", 0) or 0)),
                        "OrderQtyUOM": self.uom
                    },
                    "ProductOrItemDescription": [
                        {
                            "ProductDescription": row.get("item_name", "")
                        }
                    ],
                    "PhysicalDetails": [
                        {
                            "PackValue": 1
                        }
                    ],
                    "References": [
                        {
                        "ReferenceQual": "VIN",
                        "ReferenceID": row.get("vin", "") 
                        }          
                    ]
                }
            )

        return payload

    def write_payload_file(self, so_number, payload):
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        file_name = f"PO_940_{so_number}_{timestamp}.json"
        file_path = os.path.join(OUTPUT_FOLDER, file_name)

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=1)
            file.write("\n")

        return file_path

    def run(self):
        line_rows = self.get_sales_order_lines()
        self.logger.info("Pulled %s Sales Order SuiteQL line rows.", len(line_rows))

        grouped_sales_orders = self.group_sales_orders(line_rows)
        self.logger.info("Grouped into %s sales orders.", len(grouped_sales_orders))

        for so_internal_id, so_rows in grouped_sales_orders.items():
            so_number = so_rows[0]["tranid"]
            suiteql_pulled_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            existing_export = get_export_record(self.EXPORT_TYPE, so_internal_id)

            if existing_export and existing_export["status"] == "success":
                self.logger.info("Skipping SO %s (%s). Already exported.", so_number, so_internal_id)
                continue

            try:
                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=so_internal_id,
                    record_number=so_number,
                    status="suiteql_pulled",
                    suiteql_pulled_at=suiteql_pulled_at,
                    error_message=None,
                )

                header = self.netsuite_client.get_sales_order_header(so_internal_id)

                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=so_internal_id,
                    record_number=so_number,
                    status="header_pulled",
                    header_pulled_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    error_message=None,
                )

                payload = self.build_940_payload(header, so_rows)
                output_file = self.write_payload_file(so_number, payload)

                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=so_internal_id,
                    record_number=so_number,
                    status="success",
                    file_generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    output_file=output_file,
                    error_message=None,
                )

                self.logger.info("Successfully exported SO %s (%s) to %s", so_number, so_internal_id, output_file)

            except Exception as error:
                error_message = str(error)

                upsert_export_record(
                    export_type=self.EXPORT_TYPE,
                    record_internal_id=so_internal_id,
                    record_number=so_number,
                    status="failed",
                    error_message=error_message,
                )

                self.logger.exception("Failed exporting SO %s (%s): %s", so_number, so_internal_id, error_message)

                self.netsuite_client.send_failure_email(
                    subject=f"NetSuite Sales Order 940 Export Failure - {so_number}",
                    body=(
                        f"Failed exporting sales order.\n\n"
                        f"SO Number: {so_number}\n"
                        f"SO Internal ID: {so_internal_id}\n"
                        f"Error: {error_message}\n"
                    ),
                )