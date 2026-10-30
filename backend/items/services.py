from utilities.helpers import validation_error
from system.models import SystemStockValuationMethod
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from .stock_logger import log_stock_movement
from decimal import Decimal
from items.models import (
    BranchInventoryItemStockLayer,
)


class StockValuationService:

    @staticmethod
    def get_unit_cost(branch_item, quantity, sold_unit=None, allow_oversell=False):
        item = branch_item.inventory_item

        valuation_method = item.get_default_stock_valuation_method()
        if not valuation_method:
            try:
                valuation_method = SystemStockValuationMethod.objects.get(
                    code__iexact="FIFO"
                )
            except SystemStockValuationMethod.DoesNotExist:
                raise validation_error(
                    "System default stock valuation method not configured."
                )

        layers = (
            BranchInventoryItemStockLayer.objects.active()
            .select_for_update()
            .filter(
                branch_inventory_item=branch_item,
                quantity_remaining__gt=0,
            )
            .order_by("received_date")
        )

        method_code = valuation_method.code.upper()

        if method_code == "FIFO":
            return StockValuationService._fifo(
                layers, quantity, branch_item, sold_unit, allow_oversell
            )
        elif method_code == "LIFO":
            return StockValuationService._lifo(
                layers, quantity, branch_item, sold_unit, allow_oversell
            )
        elif method_code == "WAC":
            return StockValuationService._weighted_average(
                layers, quantity, branch_item, sold_unit, allow_oversell
            )

        raise validation_error("Unsupported stock valuation method.")

    @staticmethod
    def _fifo(layers, quantity, branch_item, sold_unit=None, allow_oversell=False):
        return StockValuationService._consume_layers(
            layers,
            quantity,
            branch_item,
            sold_unit,
            allow_oversell,
        )

    @staticmethod
    def _estimate_fifo_cost(layers):

        first_layer = layers.order_by("recieved_date").first()

        if not first_layer:
            return Decimal("0.0000")

        return Decimal(first_layer.unit_cost).quantize(Decimal("0.0001"))

    @staticmethod
    def _lifo(layers, quantity, branch_item, sold_unit=None, allow_oversell=False):
        return StockValuationService._consume_layers(
            layers.order_by("-received_date"),
            quantity,
            branch_item,
            sold_unit,
            allow_oversell,
        )

    @staticmethod
    def _estimate_lifo_cost(layers):

        latest_layer = layers.order_by("-recieved_date").first()

        if not latest_layer:
            return Decimal("0.0000")

        return Decimal(latest_layer.unit_cost).quantize(Decimal("0.0001"))

    @staticmethod
    def _weighted_average(
        layers, quantity, branch_item, sold_unit=None, allow_oversell=False
    ):
        from items.unit_converter import get_conversion_factor

        qty_needed_base = Decimal(quantity)

        if sold_unit:
            qty_needed_base *= get_conversion_factor(branch_item, sold_unit)

        total_cost = Decimal("0.00")
        total_base_available = Decimal("0.00")

        normalized_layers = []

        for layer in layers.order_by("received_date"):
            cf = (
                get_conversion_factor(branch_item, layer.unit_of_measure)
                if layer.unit_of_measure
                else Decimal("1")
            )
            base_qty = Decimal(layer.quantity_remaining) * cf

            total_base_available += base_qty
            normalized_layers.append((layer, base_qty, cf))

        if total_base_available < qty_needed_base and not allow_oversell:
            raise validation_error("Insufficient stock for valuation.")

        for layer, base_qty, cf in normalized_layers:
            if qty_needed_base <= 0:
                break

            take = min(base_qty, qty_needed_base)

            total_cost += (take / cf) * layer.unit_cost
            qty_needed_base -= take

        if qty_needed_base > 0:
            estimate = StockValuationService.estimate_negative_unit_cost(
                branch_item,
                sold_unit,
                layers,
            )

        return (total_cost / quantity).quantize(Decimal("0.0001"))

    @staticmethod
    def _estimate_wac_cost(layers):

        total_cost = Decimal("0")
        total_qty = Decimal("0")

        for layer in layers:

            qty = Decimal(layer.quantity_remaining)
            cost = Decimal(layer.unit_cost)

            total_cost += qty * cost
            total_qty += qty

        if total_qty <= 0:
            return Decimal("0.0000")

        return (total_cost / total_qty).quantize(Decimal("0.0001"))

    @staticmethod
    def _consume_layers(
        layers, quantity, branch_item, sold_unit=None, allow_oversell=False
    ):
        from items.unit_converter import get_conversion_factor

        qty_needed_base = Decimal(quantity)

        if sold_unit:
            qty_needed_base *= get_conversion_factor(branch_item, sold_unit)

        total_cost = Decimal("0.00")

        for layer in layers:
            if qty_needed_base <= 0:
                break

            layer_cf = (
                get_conversion_factor(branch_item, layer.unit_of_measure)
                if layer.unit_of_measure
                else Decimal("1")
            )

            layer_base_qty = Decimal(layer.quantity_remaining) * layer_cf
            take_base = min(layer_base_qty, qty_needed_base)

            total_cost += (take_base / layer_cf) * layer.unit_cost
            qty_needed_base -= take_base

        if qty_needed_base > 0 and not allow_oversell:
            raise validation_error("Insufficient stock for valuation.")

        if qty_needed_base > 0:
            estimate = StockValuationService.estimate_negative_unit_cost(
                branch_item,
                sold_unit,
                layers,
            )
            sold_cf = (
                get_conversion_factor(branch_item, sold_unit)
                if sold_unit
                else Decimal("1")
            )
            total_cost += (qty_needed_base / sold_cf) * estimate

        return (total_cost / quantity).quantize(Decimal("0.0001"))

    @staticmethod
    def estimate_negative_unit_cost(branch_item, sold_unit=None, positive_layers=None):
        item = branch_item.inventory_item

        if positive_layers is not None and positive_layers.exists():
            valuation_method = item.get_default_stock_valuation_method()
            method_code = valuation_method.code.upper() if valuation_method else "FIFO"

            if method_code == "LIFO":
                branch_cost = StockValuationService._estimate_branch_lifo_cost(
                    positive_layers
                )
            elif method_code == "WAC":
                branch_cost = StockValuationService._estimate_branch_wac_cost(
                    positive_layers
                )
            else:
                branch_cost = StockValuationService._estimate_branch_fifo_cost(
                    positive_layers
                )

            if branch_cost > 0:
                return branch_cost

        item_uom_queryset = item.units.filter(deleted_at__isnull=True)
        if sold_unit is not None:
            item_uom = item_uom_queryset.filter(
                unit_of_measure=sold_unit,
            ).first()
        else:
            item_uom = item_uom_queryset.filter(
                is_base_unit_of_measure=True,
            ).first()

        if item_uom is None:
            unit_name = (
                sold_unit.unit_name if sold_unit is not None else "the base unit"
            )
            raise validation_error(
                f"No unit configuration was found for '{item.item_name}' "
                f"using {unit_name}."
            )

        warehouse_cost = Decimal(item_uom.get_cost_price() or "0").quantize(
            Decimal("0.0001")
        )
        if warehouse_cost > 0:
            return warehouse_cost

        raise validation_error(
            f"No positive cost price is available for '{item.item_name}' "
            f"in {item_uom.unit_of_measure.unit_name}. "
            "Receive or add opening stock with a cost before selling below stock."
        )

    @staticmethod
    def _estimate_branch_fifo_cost(layers):
        layer = layers.order_by("received_date").first()
        return (
            Decimal(layer.unit_cost).quantize(Decimal("0.0001"))
            if layer
            else Decimal("0.0000")
        )

    @staticmethod
    def _estimate_branch_lifo_cost(layers):
        layer = layers.order_by("-received_date").first()
        return (
            Decimal(layer.unit_cost).quantize(Decimal("0.0001"))
            if layer
            else Decimal("0.0000")
        )

    @staticmethod
    def _estimate_branch_wac_cost(layers):
        total_cost = Decimal("0")
        total_qty = Decimal("0")
        for layer in layers:
            qty = Decimal(layer.quantity_remaining)
            total_cost += qty * Decimal(layer.unit_cost)
            total_qty += qty
        if total_qty <= 0:
            return Decimal("0.0000")
        return (total_cost / total_qty).quantize(Decimal("0.0001"))

    @staticmethod
    @transaction.atomic
    def apply_stock_consumption(
        branch_item,
        quantity,
        movement_type="INVOICE_SALE",
        source_document=None,
        source_reference="",
        sold_unit=None,
        allow_oversell=False,
        goods_issued_note_line=None,
    ):
        from items.unit_converter import (
            get_conversion_factor,
            decompose_base_units,
            SMALLEST_ONLY,
        )

        inventory_item = branch_item.inventory_item
        quantity = Decimal(quantity)

        institution = inventory_item.get_institution()

        try:
            breakdown_strategy = institution.unit_breakdown_strategy
        except AttributeError:
            breakdown_strategy = SMALLEST_ONLY

        if sold_unit is not None:
            sold_cf = get_conversion_factor(branch_item, sold_unit)
        else:
            sold_cf = Decimal("1")

        remaining_base = quantity * sold_cf

        layers = (
            BranchInventoryItemStockLayer.objects.select_for_update()
            .filter(
                branch_inventory_item=branch_item,
                deleted_at__isnull=True,
                quantity_remaining__gt=0,
            )
            .order_by("received_date")
        )

        for layer in layers:
            if remaining_base <= Decimal("0"):
                break

            layer_cf = (
                get_conversion_factor(branch_item, layer.unit_of_measure)
                if layer.unit_of_measure
                else Decimal("1")
            )

            layer_base_total = Decimal(layer.quantity_remaining) * layer_cf
            take_base = min(layer_base_total, remaining_base)
            qty_before = Decimal(layer.quantity_remaining)

            same_unit = (sold_unit is None) or (layer.unit_of_measure == sold_unit)

            if same_unit:
                consume_qty = take_base / layer_cf
                layer.quantity_remaining -= consume_qty
                layer.save(update_fields=["quantity_remaining"])

                log_stock_movement(
                    movement_type=movement_type,
                    inventory_item=inventory_item,
                    unit_of_measure=layer.unit_of_measure,
                    quantity_change=-consume_qty,
                    quantity_before=qty_before,
                    unit_cost=layer.unit_cost,
                    branch=branch_item.branch,
                    source_document=source_document,
                    source_reference=source_reference,
                    goods_issued_note_line=goods_issued_note_line,
                )

            else:
                full_packs = take_base // layer_cf
                leftover_base = take_base % layer_cf
                partial_pack = leftover_base > Decimal("0")
                packs_to_remove = full_packs + (
                    Decimal("1") if partial_pack else Decimal("0")
                )
                sold_quantity = take_base / sold_cf
                quantity_before_in_sold_unit = (qty_before * layer_cf) / sold_cf
                unit_cost_in_sold_unit = (Decimal(layer.unit_cost) / layer_cf) * sold_cf

                layer.quantity_remaining -= packs_to_remove
                layer.save(update_fields=["quantity_remaining"])

                log_stock_movement(
                    movement_type=movement_type,
                    inventory_item=inventory_item,
                    unit_of_measure=sold_unit,
                    quantity_change=-sold_quantity,
                    quantity_before=quantity_before_in_sold_unit,
                    unit_cost=unit_cost_in_sold_unit,
                    branch=branch_item.branch,
                    source_document=source_document,
                    source_reference=source_reference,
                    goods_issued_note_line=goods_issued_note_line,
                )

                if partial_pack:
                    remainder_base = layer_cf - leftover_base
                    base_unit_cost = layer.unit_cost / layer_cf

                    decomposed = decompose_base_units(
                        remainder_base,
                        branch_item,
                        strategy=breakdown_strategy,
                    )

                    for remainder_uom, remainder_qty in decomposed:
                        remainder_cf = get_conversion_factor(branch_item, remainder_uom)
                        prorated_cost = (base_unit_cost * remainder_cf).quantize(
                            Decimal("0.0001")
                        )

                        existing = BranchInventoryItemStockLayer.objects.filter(
                            branch_inventory_item=branch_item,
                            unit_of_measure=remainder_uom,
                            unit_cost=prorated_cost,
                            deleted_at__isnull=True,
                        ).first()

                        if existing:
                            log_qty_before = Decimal(existing.quantity_remaining)
                            existing.quantity_remaining += remainder_qty
                            existing.save(update_fields=["quantity_remaining"])
                        else:
                            log_qty_before = Decimal("0")
                            BranchInventoryItemStockLayer.objects.create(
                                branch_inventory_item=branch_item,
                                unit_of_measure=remainder_uom,
                                unit_cost=prorated_cost,
                                quantity_remaining=remainder_qty,
                                received_date=layer.received_date,
                            )

                        log_stock_movement(
                            movement_type="UNIT_BREAKDOWN",
                            inventory_item=inventory_item,
                            unit_of_measure=remainder_uom,
                            quantity_change=+remainder_qty,
                            quantity_before=log_qty_before,
                            unit_cost=prorated_cost,
                            branch=branch_item.branch,
                            source_document=source_document,
                            source_reference=source_reference,
                        )

            # if layer.quantity_remaining == 0:
            # layer.deleted_at = timezone.now()
            # layer.save(update_fields=["deleted_at", "quantity_remaining"])

            remaining_base -= take_base

        if remaining_base > Decimal("0.0001"):
            if not allow_oversell:
                raise validation_error(
                    f"Insufficient stock: {remaining_base} base units could not be fulfilled."
                )

            StockValuationService._record_oversell(
                branch_item,
                sold_unit,
                remaining_base,
                source_document,
                source_reference,
                goods_issued_note_line,
            )

    @staticmethod
    def _record_oversell(
        branch_item,
        sold_unit,
        remaining_base,
        source_document,
        source_reference,
        goods_issued_note_line=None,
    ):
        inventory_item = branch_item.inventory_item

        from items.unit_converter import get_conversion_factor

        sold_cf = (
            get_conversion_factor(branch_item, sold_unit) if sold_unit else Decimal("1")
        )
        sold_quantity = remaining_base / sold_cf
        unit_cost = StockValuationService.estimate_negative_unit_cost(
            branch_item, sold_unit
        )

        layer_queryset = (
            BranchInventoryItemStockLayer.objects.select_for_update().filter(
                branch_inventory_item=branch_item,
                unit_cost=unit_cost,
                deleted_at__isnull=True,
            )
        )

        if sold_unit is not None:
            layer_queryset = layer_queryset.filter(unit_of_measure=sold_unit)
        else:
            layer_queryset = layer_queryset.filter(unit_of_measure__isnull=True)

        layer = layer_queryset.first()

        if layer:
            layer_cf = (
                get_conversion_factor(branch_item, layer.unit_of_measure)
                if layer.unit_of_measure
                else Decimal("1")
            )
            layer_quantity = remaining_base / layer_cf
            layer_quantity_before = Decimal(layer.quantity_remaining)
            layer.quantity_remaining -= layer_quantity
            layer.save(update_fields=["quantity_remaining", "updated_at"])

            if sold_unit:
                movement_unit = sold_unit
                movement_quantity = sold_quantity
                movement_quantity_before = (layer_quantity_before * layer_cf) / sold_cf
            else:
                movement_unit = layer.unit_of_measure
                movement_quantity = layer_quantity
                movement_quantity_before = layer_quantity_before
        else:
            layer = BranchInventoryItemStockLayer.objects.create(
                branch_inventory_item=branch_item,
                unit_of_measure=sold_unit,
                unit_cost=unit_cost,
                quantity_remaining=-sold_quantity,
                received_date=timezone.now(),
            )
            movement_unit = sold_unit
            movement_quantity = sold_quantity
            movement_quantity_before = Decimal("0")

        log_stock_movement(
            movement_type="NEGATIVE_SALE",
            inventory_item=inventory_item,
            unit_of_measure=movement_unit,
            quantity_change=-movement_quantity,
            quantity_before=movement_quantity_before,
            unit_cost=unit_cost,
            branch=branch_item.branch,
            source_document=source_document,
            source_reference=source_reference,
            goods_issued_note_line=goods_issued_note_line,
        )


def get_inventory_summary(inventory_items):
    products = []

    for item in inventory_items:
        units_map = {}
        warehouse_layers = item.summary_stock_layers
        branch_items = item.summary_branch_items

        uoms = {}
        uom_map = {}
        for uom_relation in item.summary_units:
            uoms[uom_relation.unit_of_measure_id] = uom_relation.unit_of_measure
            uom_map[uom_relation.unit_of_measure.id] = uom_relation

        for branch_item in branch_items:
            for uom_relation in branch_item.summary_units:
                uoms[uom_relation.unit_of_measure_id] = uom_relation.unit_of_measure
                uom_map[uom_relation.unit_of_measure.id] = uom_relation

        warehouse_layers_by_uom = {}
        for layer in warehouse_layers:
            warehouse_layers_by_uom.setdefault(layer.unit_of_measure_id, []).append(
                layer
            )

        branch_layers_by_uom = {}
        for branch_item in branch_items:
            for layer in branch_item.summary_stock_layers:
                key = (branch_item.id, layer.unit_of_measure_id)
                branch_layers_by_uom.setdefault(key, []).append(layer)

        for uom_id, uom in uoms.items():
            uom_relation = uom_map[uom_id]
            selling_price = (
                getattr(uom_relation, "selling_price", Decimal("0"))
                if item.can_be_sold
                else Decimal("0")
            )

            units_map[uom_id] = {
                "unit_of_measure": uom.unit_name,
                "unit_abbreviation": uom.unit_abbreviation,
                "is_base_unit": getattr(uom_relation, "is_base_unit_of_measure", False),
                "selling_price": selling_price,
                "average_cost_price": getattr(
                    uom_relation, "average_cost_price", Decimal("0")
                ),
                "total_quantity": 0,
                "total_buying_price": 0,
                "total_selling_value": 0,
                "stock_locations": [],
            }
            stock_locations_map = {}

            for layer in warehouse_layers_by_uom.get(uom_id, []):
                qty = layer.quantity_remaining
                cost = qty * layer.unit_cost
                selling = qty * selling_price

                location_key = ("WAREHOUSE", "Main Warehouse")
                location = stock_locations_map.setdefault(
                    location_key,
                    {
                        "location_type": "WAREHOUSE",
                        "location_name": "Main Warehouse",
                        "quantity_remaining": Decimal("0"),
                        "unit_cost": layer.unit_cost,
                        "buying_price": Decimal("0"),
                        "selling_value": Decimal("0"),
                    },
                )
                location["quantity_remaining"] += qty
                location["buying_price"] += cost
                location["selling_value"] += selling

                units_map[uom_id]["total_quantity"] += qty
                units_map[uom_id]["total_buying_price"] += cost
                units_map[uom_id]["total_selling_value"] += selling

            for branch_item in branch_items:
                for layer in branch_layers_by_uom.get((branch_item.id, uom_id), []):
                    qty = layer.quantity_remaining
                    cost = qty * layer.unit_cost
                    selling = qty * selling_price

                    branch_name = branch_item.branch.branch_name
                    location_key = ("BRANCH", branch_name)
                    location = stock_locations_map.setdefault(
                        location_key,
                        {
                            "location_type": "BRANCH",
                            "location_name": branch_name,
                            "quantity_remaining": Decimal("0"),
                            "unit_cost": layer.unit_cost,
                            "buying_price": Decimal("0"),
                            "selling_value": Decimal("0"),
                        },
                    )
                    location["quantity_remaining"] += qty
                    location["buying_price"] += cost
                    location["selling_value"] += selling

                    units_map[uom_id]["total_quantity"] += qty
                    units_map[uom_id]["total_buying_price"] += cost
                    units_map[uom_id]["total_selling_value"] += selling

            units_map[uom_id]["stock_locations"] = list(stock_locations_map.values())

        units_data = list(units_map.values())

        product_total_quantity = sum(
            (unit["total_quantity"] for unit in units_data), Decimal("0")
        )
        product_total_buying_value = sum(
            (unit["total_buying_price"] for unit in units_data), Decimal("0")
        )
        product_total_selling_value = sum(
            (unit["total_selling_value"] for unit in units_data), Decimal("0")
        )

        response_units = [
            {
                "unit_of_measure": unit["unit_of_measure"],
                "unit_abbreviation": unit["unit_abbreviation"],
                "stock_locations": unit["stock_locations"],
            }
            for unit in units_data
        ]

        products.append(
            {
                "id": item.id,
                "base_uuid": item.base_uuid,
                "reference_code": item.reference_code,
                "item_name": item.item_name,
                "total_quantity": product_total_quantity,
                "total_buying_value": product_total_buying_value,
                "total_selling_value": product_total_selling_value,
                "category": {
                    "name": item.item_category.name if item.item_category else None,
                },
                "units_of_measure": response_units,
            }
        )

    return products
