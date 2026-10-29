"use client";

import {useState, useEffect, useRef} from "react";
import {useSearchParams} from "next/navigation";
import {useSelector} from "react-redux";
import {Icon} from "@iconify/react";
import {useModuleNavigation as useRouter} from "@/platform/v1/hooks/useModuleNavigation";
import {Button} from "@/components/ui/button";
import {Label} from "@/components/ui/label";
import {useToast} from "#/_hooks/use-toast";
import {formatCurrency, formatText, showErrorToast} from "#/_lib/utils";
import {
  INVOICES_API,
  PURCHASE_ORDERS_API,
  QUOTATIONS_API,
  CUSTOMERS_API,
  SALES_PERSON_API,
  RECURRING_INVOICES_API,
  BRANCH_INVENTORY_API,
  PAYMENT_TERMS_API,
  CURRENCIES_API,
} from "#/_api/api.helpers";
import {
  IInvoiceFormData,
  IPurchaseOrder,
  IQuotation,
  ICustomer,
  ISalesPerson,
  IRecurringInvoice,
  Currency,
  IPaymentTerm,
} from "#/_types/api.types";
import {selectSelectedInstitution} from "@/store/auth/selectors";
import PaginatedSearchableSelect from "#/_components/custom/paginated-searchable-select";
import PageLayout from "#/_components/common/layouts/page-layout";
import {type SaveAction, SaveActionButton} from "#/_components/common/save-action-button";
import LineItemsInput from "#/_components/custom/sales/line-items-input";
import FormSection from "#/_components/common/form-section";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {RadioGroup, RadioGroupItem} from "@/components/ui/radio-group";
import FormattedNumberInput from "#/_components/common/inputs/formatted-number-input";
import React from "react";
import {ICashAccount} from "#/_types/approvals.types";
import CashAccountSelect from "#/_components/custom/cash-account-select";
import {Textarea} from "@/components/ui/textarea";
import {CreateCustomerPanel} from "#/_components/common/create-customer-panel";
import {FEATURE_CODES} from "#/_constants/features.enum";
import ProtectedComponent from "#/_components/custom/protected-component";
import FormattedDatePicker from "#/_components/common/inputs/formatted-date-picker";
import {CURRENCY_CONVERSION_API, IExchangeRateInput} from "#/_api/services/system.service";
import ExchangeRateInput from "#/_components/custom/exchange-rate-input";

type PaymentStatus = "paid" | "unpaid" | "partially_paid";
type SourceType = "none" | "purchase_order" | "quotation" | "recurring";

const sourceOptions: {
  value: SourceType;
  label: string;
  icon: string;
  feature?: FEATURE_CODES;
}[] = [
  {
    value: "purchase_order",
    label: "Sales Order",
    icon: "hugeicons:shopping-cart-01",
    feature: FEATURE_CODES.FEATURE_SALES_ORDERS,
  },
  {
    value: "quotation",
    label: "Quotation",
    icon: "hugeicons:file-02",
    feature: FEATURE_CODES.FEATURE_QUOTATIONS,
  },
  {
    value: "recurring",
    label: "Recurring",
    icon: "hugeicons:repeat",
  },
];

const fetchAllQuotationItems = async (quotationUuid: string) => {
  let page = await QUOTATIONS_API.fetchQuotationLineItems({
    quotationBaseUuid: quotationUuid,
    page: 1,
  });
  const items = [...page.results];

  while (page.next) {
    page = await QUOTATIONS_API.fetchQuotationLineItemsFromUrl({
      url: page.next,
    });
    items.push(...page.results);
  }

  return items;
};

export default function InvoiceCreatePage() {
  const router = useRouter();
  const {toast} = useToast();
  const currentInstitution = useSelector(selectSelectedInstitution);
  const searchParams = useSearchParams();
  const purchaseOrderIdFromQuery = searchParams.get("purchaseOrderId");
  const quotationIdFromQuery = searchParams.get("quotationId");
  const [sourceType, setSourceType] = useState<SourceType>("none");
  const [purchaseOrder, setPurchaseOrder] = useState<IPurchaseOrder | null>(null);
  const purchaseOrderRequestId = useRef(0);
  const [loadingPurchaseOrder, setLoadingPurchaseOrder] = useState(false);
  const [quotation, setQuotation] = useState<IQuotation | null>(null);
  const [customer, setCustomer] = useState<ICustomer | null>(null);
  const [querySelectedPO, setQuerySelectedPO] = useState<IPurchaseOrder | null>(null);
  const [querySelectedQO, setQuerySelectedQO] = useState<IQuotation | null>(null);
  const [recurringTemplate, setRecurringTemplate] = useState<IRecurringInvoice | null>(null);
  const [selectedCashAccount, setSelectedCashAccount] = useState<ICashAccount | null>(null);
  const [lineItemsKey, setLineItemsKey] = useState(0);
  const [selectedCustomer, setSelectedCustomer] = useState<ICustomer | null>(null);
  const [preselectedCustomerLabel, setPreselectedCustomerLabel] = useState<string | undefined>();
  const [selectedPaymentTerm, setSelectedPaymentTerm] = useState<IPaymentTerm | null>(null);
  const [documentCurrencyMultiplier, setDocumentCurrencyMultiplier] = useState(1);
  const [currencyConversionReady, setCurrencyConversionReady] = useState(true);
  const [selectedInvoiceCurrency, setSelectedInvoiceCurrency] = useState<Currency | null>(null);

  const [formData, setFormData] = useState<IInvoiceFormData>({
    customer: "" as any,
    purchase_order: "" as any,
    quotation: "" as any,
    issue_date: new Date().toISOString().split("T")[0],
    line_items: [],
    global_tax_ids: [],
    invoice_payment_status: "unpaid",
    sales_person: "" as any,
    description: "",
    cash_account: undefined,
    payment_term: undefined,
    exchange_rate: null,
  });
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [saveAction, setSaveAction] = useState<SaveAction>("save-and-view");
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus>("unpaid");
  const [partialAmount, setPartialAmount] = useState("");
  const [showCreateCustomer, setShowCreateCustomer] = useState(false);
  const [paymentErrors, setPaymentErrors] = useState<Record<string, string>>({});
  const fetchRecurringInvoices = React.useCallback(
    async (q: any) =>
      await RECURRING_INVOICES_API.fetchRecurringInvoices({
        ...q,
        status: "active",
        active_without_ongoing_approval: true,
      }),
    [],
  );
  const fetchPaymentTerms = React.useCallback(
    ({search}: any) => PAYMENT_TERMS_API.fetchPaymentTerms({page: 1, search}),
    [],
  );

  useEffect(() => {
    const raw = sessionStorage.getItem("duplicate_invoice");
    if (!raw) return;

    const hydrateDuplicate = async () => {
      const duplicated = JSON.parse(raw);

      if (duplicated.customerData) {
        setCustomer(duplicated.customerData);
        setFormData((prev) => ({...prev, customer: duplicated.customerData.base_uuid}));
      }

      if (duplicated.line_items?.length) {
        const enrichedItems = await Promise.all(
          duplicated.line_items.map(async (item: any) => {
            const fullItem = await BRANCH_INVENTORY_API.fetchBranchInventoryItemById({
              item_uuid: item.item_base_uuid,
            });
            const units = fullItem.branch_inventory_item_units_of_measure ?? [];
            const selectedUom =
              units.find((unit) => unit.base_uuid === item.unit_of_measure_base_uuid) ??
              units.find((unit) => unit.is_base_unit_of_measure) ??
              units[0];
            const unitPrice =
              selectedUom?.selling_price?.toString() ?? fullItem.selling_price?.toString() ?? "0";
            const quantity = Number(item.quantity || 1);

            return {
              line_item: fullItem,
              quantity,
              unit_price: unitPrice,
              unit_of_measure: selectedUom,
              line_total: (quantity * Number(unitPrice)).toFixed(2),
            };
          }),
        );
        const mapped = await mapLineItems(enrichedItems);
        setFormData((prev) => ({...prev, line_items: mapped}));
        setLineItemsKey((k) => k + 1);
      }
    };

    hydrateDuplicate()
      .catch(() => {})
      .finally(() => {
        sessionStorage.removeItem("duplicate_invoice");
      });
  }, []);

  useEffect(() => {
    const prefillFromPurchaseOrder = async () => {
      if (!purchaseOrderIdFromQuery) {
        setLoading(false);
        return;
      }

      const requestId = ++purchaseOrderRequestId.current;
      setLoadingPurchaseOrder(true);
      setLoading(true);
      try {
        const [po, poItems] = await Promise.all([
          PURCHASE_ORDERS_API.fetchPurchaseOrderById({
            purchaseOrderUuid: purchaseOrderIdFromQuery,
          }),
          PURCHASE_ORDERS_API.fetchPurchaseOrderLineItems({
            purchaseOrderUuid: purchaseOrderIdFromQuery,
          }),
        ]);

        const lineItems = await mapLineItems(poItems.results);
        if (requestId !== purchaseOrderRequestId.current) return;

        setSourceType("purchase_order");
        setPurchaseOrder(po);
        setQuerySelectedPO(po);
        const poCustomer = po.customer ?? po.quotation?.customer ?? null;
        setCustomer(poCustomer);
        setSelectedCustomer(poCustomer);
        setPreselectedCustomerLabel(poCustomer?.customer_name);

        setFormData((prev) => ({
          ...prev,
          purchase_order: po.base_uuid,
          customer: poCustomer?.base_uuid ?? "",
          line_items: lineItems,
        }));
      } catch (error) {
        if (requestId !== purchaseOrderRequestId.current) return;
        showErrorToast({defaultMessage: "Failed to fetch the selected sales order.", error});
      } finally {
        if (requestId === purchaseOrderRequestId.current) {
          setLoadingPurchaseOrder(false);
        }
        setLoading(false);
      }
    };

    prefillFromPurchaseOrder();
    return () => {
      purchaseOrderRequestId.current += 1;
    };
  }, [purchaseOrderIdFromQuery, currentInstitution]);

  useEffect(() => {
    const prefillFromQuotation = async () => {
      if (!quotationIdFromQuery) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const [qo, quotationItems] = await Promise.all([
          QUOTATIONS_API.fetchQuotationById({
            quotationUuid: quotationIdFromQuery,
          }),
          fetchAllQuotationItems(quotationIdFromQuery),
        ]);

        setSourceType("quotation");
        setQuotation(qo);
        setQuerySelectedQO(qo);
        setCustomer(qo?.customer);

        const lineItems = await mapLineItems(quotationItems);

        setFormData((prev) => ({
          ...prev,
          quotation: qo.base_uuid,
          customer: qo?.customer?.base_uuid ?? "",
          line_items: lineItems,
        }));
      } catch (error) {
        showErrorToast({defaultMessage: "Failed to fetch the selected quotation.", error});
      } finally {
        setLoading(false);
      }
    };

    prefillFromQuotation();
  }, [quotationIdFromQuery, currentInstitution]);

  const mapLineItems = async (items: any[] = []) => {
    return await Promise.all(
      items.map(async (item: any) => {
        const originalPrice = parseFloat(item.unit_price || item.price || "0").toFixed(2);

        let displayPrice = originalPrice;
        let netPrice = originalPrice;
        let taxPrice = "0";
        let taxBaseUuid = "";
        let taxType = "";

        const baseUuid = item.line_item?.base_uuid;

        if (baseUuid) {
          try {
            const taxResponse = await INVOICES_API.previewTaxCalculation({
              amount: originalPrice,
              base_uuid: baseUuid,
              type: "sales",
            });
            displayPrice = taxResponse.gross_amount.toString();
            netPrice = taxResponse.net_amount.toString();
            taxPrice = taxResponse.tax_amount.toString();
            taxBaseUuid = baseUuid;
            taxType = "sales";
          } catch {}
        }

        const discounts = (item.discounts ?? []).map((d) => ({
          id: d.id,
          discount_type: d.discount_type,
          discount_value: d.discount_value,
          position: d.position,
          description: d.description,
        }));

        return {
          type: "inventory" as const,
          item: {
            ...item.line_item,
            base_uuid: item.line_item?.base_uuid,
          },
          line_item: item.line_item?.base_uuid ?? "",
          item_name: item.line_item?.inventory_item?.item_name ?? "",
          item_category: item.line_item?.item_category?.name ?? "",
          quantity: item.quantity || 1,
          quantity_issued: item.quantity_issued ?? 0,
          unit_price: originalPrice,
          net_unit_price: netPrice,
          tax_unit_price: taxPrice,
          display_unit_price: displayPrice,
          tax_base_uuid: taxBaseUuid,
          tax_type: taxType,
          unit_of_measure: item.unit_of_measure?.base_uuid || item.unit_of_measure || "",
          selected_uom_uuid: item.unit_of_measure?.base_uuid || "",
          line_total: parseFloat(item.line_total || "0").toFixed(2),
          discounts,
        };
      }),
    );
  };
  const normalizeCurrency = (currency: string | Currency | null | undefined): Currency | null => {
    if (!currency || typeof currency === "string") return null;
    return currency;
  };

  const sourceCurrency =
    normalizeCurrency(purchaseOrder?.currency) ?? normalizeCurrency(quotation?.currency);
  const documentCurrency =
    sourceCurrency ??
    customer?.currency ??
    selectedInvoiceCurrency ??
    currentInstitution?.currency ??
    null;
  const isForeignCurrencyInvoice =
    !!documentCurrency &&
    !!currentInstitution?.currency &&
    documentCurrency.id !== currentInstitution.currency.id;
  const usesBaseCurrencyInput =
    (sourceType === "none" || sourceType === "recurring") && isForeignCurrencyInvoice;
  const activeExchangeRate = formData.exchange_rate ?? undefined;

  const handleExchangeRateChange = React.useCallback(
    (exchangeRate: IExchangeRateInput | undefined) => {
      setFormData((prev) => ({...prev, exchange_rate: exchangeRate}));
    },
    [],
  );

  useEffect(() => {
    if (!usesBaseCurrencyInput || !documentCurrency) {
      setDocumentCurrencyMultiplier(1);
      setCurrencyConversionReady(true);
      return;
    }

    let cancelled = false;
    setCurrencyConversionReady(false);

    CURRENCY_CONVERSION_API.post({
      amount: "1",
      currency: documentCurrency.id.toString(),
      ...(activeExchangeRate ? {exchange_rate: activeExchangeRate} : {}),
    })
      .then((result) => {
        if (cancelled) return;
        setDocumentCurrencyMultiplier(Number(result.converted_amount));
        setCurrencyConversionReady(true);
      })
      .catch(() => {
        if (cancelled) return;
        setDocumentCurrencyMultiplier(1);
        setCurrencyConversionReady(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeExchangeRate, documentCurrency, usesBaseCurrencyInput]);

  const calculateTotal = () => {
    const inputCurrencyTotal = formData.line_items.reduce((sum, item) => {
      const total = (item as any).display_line_total || item.line_total;
      return sum + parseFloat(total || "0");
    }, 0);

    return usesBaseCurrencyInput
      ? inputCurrencyTotal * documentCurrencyMultiplier
      : inputCurrencyTotal;
  };

  const handleSourceTypeChange = (type: SourceType) => {
    purchaseOrderRequestId.current += 1;
    setLoadingPurchaseOrder(false);
    setCustomer(null);
    setSelectedCustomer(null);
    setPreselectedCustomerLabel(undefined);
    setSourceType(type);
    setPurchaseOrder(null);
    setQuotation(null);
    setRecurringTemplate(null);
    setSelectedInvoiceCurrency(null);
    setLineItemsKey((k) => k + 1);

    setFormData((prev) => ({
      ...prev,
      purchase_order: "" as any,
      quotation: "" as any,
      customer: "",
      line_items: [],
      exchange_rate: null,
    }));
  };

  const handlePurchaseOrderChange = async (po: IPurchaseOrder) => {
    const requestId = ++purchaseOrderRequestId.current;
    setLoadingPurchaseOrder(true);
    setPurchaseOrder(po);
    setCustomer(null);
    setSelectedCustomer(null);
    setPreselectedCustomerLabel(undefined);
    setSelectedInvoiceCurrency(null);
    setLineItemsKey((k) => k + 1);
    setFormData((prev) => ({
      ...prev,
      purchase_order: po.base_uuid,
      customer: "",
      line_items: [],
      exchange_rate: null,
    }));

    try {
      const [fullOrder, response] = await Promise.all([
        PURCHASE_ORDERS_API.fetchPurchaseOrderById({
          purchaseOrderUuid: po.base_uuid,
        }),
        PURCHASE_ORDERS_API.fetchPurchaseOrderLineItems({
          purchaseOrderUuid: po.base_uuid,
        }),
      ]);
      const lineItems = await mapLineItems(response.results);
      if (requestId !== purchaseOrderRequestId.current) return;

      const poCustomer = fullOrder.customer ?? fullOrder.quotation?.customer ?? null;
      setCustomer(poCustomer);
      setSelectedCustomer(poCustomer);
      setPreselectedCustomerLabel(poCustomer?.customer_name);
      setPurchaseOrder({...fullOrder, line_items: response.results});
      setFormData((prev) => ({
        ...prev,
        purchase_order: fullOrder.base_uuid,
        customer: poCustomer?.base_uuid ?? "",
        line_items: lineItems,
        exchange_rate: null,
      }));
      setLineItemsKey((k) => k + 1);
    } catch (error) {
      if (requestId !== purchaseOrderRequestId.current) return;
      setPurchaseOrder(null);
      setFormData((prev) => ({...prev, purchase_order: ""}));
      showErrorToast({defaultMessage: "Failed to load the selected sales order.", error});
    } finally {
      if (requestId === purchaseOrderRequestId.current) {
        setLoadingPurchaseOrder(false);
      }
    }
  };

  const handleQuotationChange = async (quot: IQuotation) => {
    if (quot?.customer) setCustomer(quot.customer);

    const quotationItems = await fetchAllQuotationItems(quot.base_uuid);
    const lineItems = await mapLineItems(quotationItems);

    setFormData((prev) => ({
      ...prev,
      quotation: quot?.base_uuid,
      customer: quot?.customer?.base_uuid,
      line_items: lineItems,
      exchange_rate: null,
    }));
    setQuotation(quot);
    setLineItemsKey((k) => k + 1);
  };

  const handleRecurringInvoiceChange = async (template: IRecurringInvoice) => {
    const recurringItems = await RECURRING_INVOICES_API.fetchRecurringInvoiceItems({
      recurringInvoiceUuid: template.base_uuid,
    });

    const mappedLineItems = await Promise.all(
      recurringItems.map(async (item: any) => {
        const originalPrice = parseFloat(item.unit_cost || "0").toFixed(2);

        let displayPrice = originalPrice;
        let netPrice = originalPrice;
        let taxPrice = "0";
        let taxBaseUuid = "";
        let taxType = "";
        let branchItemUuid = "";
        try {
          const branchItems = await BRANCH_INVENTORY_API.fetchBranchInventory({
            query: {search: item.line_item?.item_name ?? ""},
            page: 1,
          });
          const match = branchItems.results.find(
            (b: any) => b.inventory_item?.id === item.line_item?.id,
          );
          if (match) branchItemUuid = match.base_uuid;
        } catch {}

        if (branchItemUuid) {
          try {
            const taxResponse = await INVOICES_API.previewTaxCalculation({
              amount: originalPrice,
              base_uuid: branchItemUuid,
              type: "sales",
            });
            displayPrice = taxResponse.gross_amount.toString();
            netPrice = taxResponse.net_amount.toString();
            taxPrice = taxResponse.tax_amount.toString();
            taxBaseUuid = branchItemUuid;
            taxType = "sales";
          } catch {}
        }

        return {
          type: "inventory" as const,
          item: {
            id: item.line_item?.id,
            inventory_item: {
              item_name: item.line_item?.item_name,
              item_code: item.line_item?.item_code,
            },
            item_name: item.line_item?.item_name,
            item_code: item.line_item?.item_code,
            quantity: parseFloat(item.quantity || "0"),
            branch_inventory_item: {
              id: item.line_item?.id,
              item_name: item.line_item?.item_name,
              item_code: item.line_item?.item_code,
            },
            branch_inventory_item_units_of_measure: item.unit_of_measure
              ? [
                  {
                    base_uuid: item.unit_of_measure.base_uuid,
                    unit_of_measure: {
                      unit_name: item.unit_of_measure.unit_name,
                      unit_abbreviation: item.unit_of_measure.unit_abbreviation || "",
                    },
                    selling_price: originalPrice,
                    is_base_unit_of_measure: true,
                  },
                ]
              : [],
          },
          line_item: branchItemUuid,
          item_name: item.line_item?.item_name ?? "",
          quantity: parseFloat(item.quantity || "0"),
          quantity_issued: 0,
          unit_price: originalPrice,
          net_unit_price: netPrice,
          tax_unit_price: taxPrice,
          display_unit_price: displayPrice,
          tax_base_uuid: taxBaseUuid,
          tax_type: taxType,
          line_total: (parseFloat(item.quantity || "0") * parseFloat(displayPrice)).toFixed(2),
          selected_uom_uuid: item.unit_of_measure?.base_uuid || "",
          unit_of_measure: item.unit_of_measure?.base_uuid || "",
        };
      }),
    );
    setRecurringTemplate(template);
    setFormData((prev) => ({
      ...prev,
      customer: template?.customer?.base_uuid,
      line_items: mappedLineItems,
      exchange_rate: null,
    }));
    setLineItemsKey((k) => k + 1);

    if (template?.customer?.id) {
      try {
        const customersResponse = await CUSTOMERS_API.fetchCustomers({
          page: 1,
          search: template.customer.customer_name,
        });
        const fullCustomer = customersResponse.results.find((c) => c.id === template.customer.id);
        setCustomer(fullCustomer ?? (template.customer as ICustomer));
      } catch {
        setCustomer(template.customer as ICustomer);
      }
    }
  };
  const handleCustomerChange = (cust: ICustomer | null) => {
    setCustomer(cust);
    if (cust) {
      setSelectedInvoiceCurrency(null);
    }
    setFormData((prev) => ({
      ...prev,
      customer: cust?.base_uuid ?? "",
      exchange_rate: null,
    }));
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (loadingPurchaseOrder) {
      newErrors.purchase_order = "Wait for the selected sales order to finish loading.";
    }
    if (paymentStatus !== "paid" && !formData.customer) {
      newErrors.customer = "Select a customer for an unpaid or partially paid invoice.";
    }

    if (!formData.issue_date) {
      newErrors.issue_date = "Issue date is required";
    }

    if (!formData.line_items || formData.line_items.length === 0) {
      newErrors.line_items = "At least one line item is required";
    }

    if (usesBaseCurrencyInput && !currencyConversionReady) {
      newErrors.line_items = `A valid ${documentCurrency?.code ?? "foreign-currency"} exchange rate is required.`;
    }

    const incompleteManufacturingItem = formData.line_items.find(
      (item) =>
        item.should_auto_create_manufacturing_order &&
        (!item.qty_to_be_manufactured || item.qty_to_be_manufactured < 1),
    );

    if (incompleteManufacturingItem) {
      newErrors.line_items = "Complete the manufacturing details for every selected item";
    }

    if (sourceType === "purchase_order" && !formData.purchase_order) {
      newErrors.purchase_order = "Please select a sales order";
    }

    if (sourceType === "quotation" && !formData.quotation) {
      newErrors.quotation = "Please select a quotation";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validatePayment = () => {
    const newErrors: Record<string, string> = {};
    const total = calculateTotal();

    if (paymentStatus === "partially_paid") {
      const amount = parseFloat(partialAmount);

      if (!partialAmount || amount <= 0) {
        newErrors.partialAmount = "Please enter a valid partial payment amount";
      } else if (amount >= total) {
        newErrors.partialAmount = "Partial payment must be less than the total amount";
      }
    }

    if (paymentStatus !== "unpaid" && !formData.cash_account) {
      newErrors.cash_account = "Please select the cash account that received this payment";
    }

    setPaymentErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (
    event?: React.FormEvent<HTMLFormElement>,
    action: SaveAction = "save-and-view",
  ) => {
    event?.preventDefault();

    if (!validateForm()) {
      showErrorToast({
        defaultMessage: "Please fill in all required fields before submitting.",
      });
      return;
    }

    if (!currentInstitution) {
      toast({
        title: "Error",
        description: "No institution selected",
        variant: "destructive",
      });
      return;
    }

    setSaveAction(action);
    setShowPaymentModal(true);
  };

  const handleFinalSubmit = async () => {
    if (!validatePayment()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: IInvoiceFormData = {
        ...formData,
        ...(sourceType === "none" && !customer && selectedInvoiceCurrency
          ? {currency: selectedInvoiceCurrency.id}
          : {}),
        customer: formData.customer || undefined,
        purchase_order:
          sourceType === "purchase_order" ? formData.purchase_order || undefined : undefined,
        quotation: sourceType === "quotation" ? formData.quotation || undefined : undefined,
        recurring_invoice: sourceType === "recurring" ? recurringTemplate?.base_uuid : undefined,
        payment_term: formData.payment_term || undefined,
        invoice_payment_status: paymentStatus,
        partial_amount_paid:
          paymentStatus === "partially_paid" ? parseFloat(partialAmount) : undefined,
        cash_account: paymentStatus === "unpaid" ? undefined : formData.cash_account,
        ...(formData.exchange_rate ? {exchange_rate: formData.exchange_rate} : {}),
        line_items: formData.line_items.map((item) => ({
          type: item.type,
          line_item: String(item.line_item),
          item_name: item.item_name,
          item_category: item.item_category,
          quantity: Number(item.quantity),
          quantity_issued: Number(item.quantity_issued),
          unit_price: item.unit_price,
          line_total: item.line_total,
          unit_of_measure: item.unit_of_measure,
          tax_base_uuid: item.tax_base_uuid || undefined,
          tax_type: item.tax_type || undefined,
          should_auto_create_manufacturing_order:
            item.should_auto_create_manufacturing_order || false,
          bill_of_material_to_be_used: item.bill_of_material_to_be_used || undefined,
          qty_to_be_manufactured: item.qty_to_be_manufactured || undefined,
          manufacturing_order_description:
            item.manufacturing_order_description?.trim() || undefined,
          discounts: item.discounts,
        })),
      };

      const createdInvoice = await INVOICES_API.createInvoice({invoiceData: payload});

      toast({
        title: "Success",
        description: "Invoice created successfully",
      });

      if (saveAction === "save-and-new") {
        window.location.assign("/invoices/create");
      } else if (saveAction === "save-and-close") {
        router.push("/invoices");
      } else {
        router.push(`/invoices/${createdInvoice.base_uuid}`);
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.message || "Failed to create invoice",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
      setShowPaymentModal(false);
    }
  };

  const fetchCustomers = React.useCallback(
    async (q: any) =>
      await CUSTOMERS_API.fetchCustomers({...q, active_without_ongoing_approval: true}),
    [],
  );

  const fetchSalesPersons = React.useCallback(
    async (q: any) => await SALES_PERSON_API.fetchSalesPersons({...q}),
    [],
  );

  const fetchPurchaseOrders = React.useCallback(
    async (q: any) =>
      await PURCHASE_ORDERS_API.fetchPurchaseOrders({
        ...q,
        get_only_not_full_invoiced: true,
        active_without_ongoing_approval: true,
      }),
    [],
  );

  const fetchQuotations = React.useCallback(
    async (q: any) =>
      await QUOTATIONS_API.fetchQuotations({
        ...q,
        status: "approved",
        active_without_ongoing_approval: true,
      }),
    [],
  );

  // Early returns
  if (!currentInstitution) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">Please select an institution to create invoices.</p>
      </div>
    );
  }

  return (
    <PageLayout title="Create an Invoice">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="icon"
          className="rounded-full"
          onClick={() => router.push("/invoices?tab=list")}
        >
          <Icon icon="hugeicons:arrow-left-02" className="size-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Create New Invoice</h1>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-4 bg-gray-200 animate-pulse rounded" />
          ))}
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-2">
          {/* Section 1: Invoice Source */}
          <FormSection
            title="Invoice Source"
            description="Choose whether to link this invoice to an existing sales order, quotation, or create from scratch."
          >
            <div className="space-y-2 w-full">
              <Label showOptional>Source Document</Label>
              <div className="grid grid-cols-3 rounded-xl bg-muted p-1">
                {sourceOptions.map((option) => {
                  const selector = (
                    <button
                      type="button"
                      aria-pressed={sourceType === option.value}
                      onClick={() =>
                        handleSourceTypeChange(sourceType === option.value ? "none" : option.value)
                      }
                      className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                        sourceType === option.value
                          ? "bg-background text-primary shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      <Icon icon={option.icon} className="size-5" />
                      <span className="hidden lg:inline">{option.label}</span>
                    </button>
                  );

                  return option.feature ? (
                    <ProtectedComponent key={option.value} permissionCode={option.feature}>
                      {selector}
                    </ProtectedComponent>
                  ) : (
                    <React.Fragment key={option.value}>{selector}</React.Fragment>
                  );
                })}
              </div>
              <p className="text-sm text-muted-foreground">
                {sourceType === "none"
                  ? "Create this invoice without linking a source document."
                  : `Create this invoice from a linked ${
                      sourceOptions.find((option) => option.value === sourceType)?.label
                    }.`}
              </p>
            </div>

            {/* Purchase Order Selection */}
            {sourceType === "purchase_order" && (
              <div className="space-y-2 pl-4 pr-4 border-l-2 border-primary w-full max-w-xl mx-auto">
                <Label htmlFor="sales_order" required>
                  Select Sales Order
                </Label>
                <PaginatedSearchableSelect<IPurchaseOrder>
                  key={querySelectedPO?.base_uuid || "no-sales-order"}
                  fetchFirstPage={fetchPurchaseOrders}
                  fetchFromUrl={PURCHASE_ORDERS_API.fetchPurchaseOrdersFromUrl}
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  value={purchaseOrder?.base_uuid || null}
                  labelKey="reference_code"
                  labelDescKeyFn={(item) =>
                    `${formatText(item.approval_status ?? "")} · ${formatText(item.invoice_status ?? "")}`
                  }
                  initialData={querySelectedPO ? [querySelectedPO] : undefined}
                  onValueChange={() => {}}
                  onItemsChange={(list) => {
                    if (!list[0]) {
                      purchaseOrderRequestId.current += 1;
                      setLoadingPurchaseOrder(false);
                      setPurchaseOrder(null);
                      setCustomer(null);
                      setSelectedCustomer(null);
                      setPreselectedCustomerLabel(undefined);
                      setLineItemsKey((k) => k + 1);
                      setFormData((prev) => ({
                        ...prev,
                        purchase_order: "" as any,
                        customer: "" as any,
                        line_items: [],
                        exchange_rate: null,
                      }));
                      return;
                    }
                    handlePurchaseOrderChange(list[0]);
                  }}
                  placeholder="Select sales order"
                  searchPlaceholder="Search sales orders..."
                  emptyMessage="No approved sales orders found"
                  description="Selecting a sales order will auto-fill line items and customer information."
                />
                {errors.purchase_order && (
                  <p className="text-sm text-red-600">{errors.purchase_order}</p>
                )}
              </div>
            )}
            {/* Quotation Selection */}
            {sourceType === "quotation" && (
              <div className="space-y-2 pl-4 pr-4 border-l-2 border-primary w-full max-w-xl mx-auto">
                <Label htmlFor="quotation" required>
                  Select Quotation
                </Label>
                <PaginatedSearchableSelect<IQuotation>
                  fetchFirstPage={fetchQuotations}
                  fetchFromUrl={QUOTATIONS_API.fetchQuotationsFromUrl}
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  labelKey="reference_code"
                  key={querySelectedQO?.base_uuid || "no-quotation"}
                  value={quotation?.base_uuid || null}
                  labelDescKey="status"
                  initialData={querySelectedQO ? [querySelectedQO] : undefined}
                  onValueChange={() => {}}
                  onItemsChange={(list) => {
                    if (!list[0]) {
                      setQuotation(null);
                      setCustomer(null);
                      setLineItemsKey((k) => k + 1);
                      setFormData((prev) => ({
                        ...prev,
                        quotation: "" as any,
                        customer: "" as any,
                        line_items: [],
                      }));
                      return;
                    }
                    handleQuotationChange(list[0]);
                  }}
                  placeholder="Select quotation"
                  searchPlaceholder="Search quotations..."
                  emptyMessage="No approved quotations found"
                  description="Selecting a quotation will auto-fill line items and customer information."
                />
                {errors.quotation && <p className="text-sm text-red-600">{errors.quotation}</p>}
              </div>
            )}

            {/* Recurring Invoice Selection */}
            {sourceType === "recurring" && (
              <div className="space-y-2 pl-4 pr-4 border-l-2 border-primary w-full max-w-xl mx-auto">
                <Label htmlFor="recurring_template" required>
                  Select Recurring Invoice Template
                </Label>
                <PaginatedSearchableSelect<IRecurringInvoice>
                  fetchFirstPage={fetchRecurringInvoices}
                  fetchFromUrl={RECURRING_INVOICES_API.fetchRecurringInvoicesFromUrl}
                  idKey="base_uuid"
                  valueKey="base_uuid"
                  labelKey="reference_code"
                  labelKeyFn={(item) => item.reference_code || item.name || `Template #${item.id}`}
                  labelDescKeyFn={(item) =>
                    `${item.customer?.customer_name} - ${item.recurring_frequency}`
                  }
                  onValueChange={(list) => {
                    if (!list || list.length === 0) {
                      setRecurringTemplate(null);
                      setCustomer(null);
                      setFormData((prev) => ({
                        ...prev,
                        customer: "" as any,
                        line_items: [],
                      }));
                    }
                  }}
                  onItemsChange={(list) => {
                    if (!list[0]) {
                      setRecurringTemplate(null);
                      setLineItemsKey((k) => k + 1);
                      setCustomer(null);
                      setFormData((prev) => ({
                        ...prev,
                        customer: "" as any,
                        line_items: [],
                      }));
                      return;
                    }
                    handleRecurringInvoiceChange(list[0]);
                  }}
                  placeholder="Select recurring invoice template"
                  searchPlaceholder="Search templates..."
                  emptyMessage="No active recurring invoice templates found"
                  description="Selecting a template will auto-fill line items and customer information from the recurring invoice."
                />
                {errors.recurring_template && (
                  <p className="text-sm text-red-600">{errors.recurring_template}</p>
                )}
              </div>
            )}
          </FormSection>

          {/* Section 2: Invoice Details */}
          <FormSection
            title="Invoice Details"
            description="Specify the customer and key invoice information."
          >
            <div>
              <Label
                htmlFor="customer"
                required={paymentStatus !== "paid"}
                showOptional={paymentStatus === "paid"}
              >
                Customer
              </Label>
              <PaginatedSearchableSelect<ICustomer>
                key={`customer-${sourceType}-${customer?.base_uuid || "none"}`}
                fetchFirstPage={fetchCustomers}
                fetchFromUrl={CUSTOMERS_API.fetchCustomersFromUrl}
                idKey="base_uuid"
                valueKey="base_uuid"
                labelKey="customer_name"
                labelDescKeyFn={(cust) => cust.email || cust.phone_number || ""}
                value={customer?.base_uuid ?? null}
                initialData={customer ? [customer] : []}
                initialSelectedLabel={preselectedCustomerLabel}
                onValueChange={() => {}}
                onItemSelected={(item) => {
                  handleCustomerChange(item);
                  setSelectedCustomer(item);
                  setPreselectedCustomerLabel(item?.customer_name);
                }}
                placeholder="Select customer"
                searchPlaceholder="Search customers..."
                emptyMessage="No customers found"
                description="The customer receiving this invoice. Will be auto-filled if you selected a sales order or quotation."
                disabled={
                  loadingPurchaseOrder ||
                  (sourceType === "purchase_order"
                    ? Boolean(purchaseOrder?.customer ?? purchaseOrder?.quotation?.customer)
                    : sourceType !== "none")
                }
                createAction={{
                  label: "Create new customer",
                  onClick: () => setShowCreateCustomer(true),
                }}
              />
              {errors.customer && <p className="text-sm text-red-600">{errors.customer}</p>}
            </div>
            {/* {!formData.customer && (
              <div>
                <Label htmlFor="sales_person" showOptional>
                  Sales Person
                </Label>
                <PaginatedSearchableSelect<ISalesPerson>
                  fetchFirstPage={fetchSalesPersons}
                  fetchFromUrl={SALES_PERSON_API.fetchSalesPersonFromUrl}
                  idKey="id"
                  valueKey="id"
                  labelKey="name"
                  labelDescKey="email"
                  onValueChange={() => {}}
                  placeholder="Select sales person"
                  searchPlaceholder="Search sales persons..."
                  emptyMessage="No sales persons found"
                  description="The sales person associated with this invoice."
                />
                {errors.sales_person && (
                  <p className="text-sm text-red-600">{errors.sales_person}</p>
                )}
              </div>
            )} */}

            <div>
              <FormattedDatePicker
                value={formData.issue_date}
                onChange={(value) => setFormData((prev) => ({...prev, issue_date: value || ""}))}
                id="issue_date"
                label="Issue Date"
                required={true}
                showAsterisk={true}
                maxDate={new Date()}
                limitMaxWidth={false}
                inputClassName="w-full bg-card border-border/50 h-10"
              />
              {errors.issue_date && <p className="text-sm text-red-600">{errors.issue_date}</p>}
            </div>

            <div>
              <Label htmlFor="payment_term" showOptional>
                Payment Terms
              </Label>
              <PaginatedSearchableSelect<IPaymentTerm>
                idKey="base_uuid"
                valueKey="base_uuid"
                labelKey="term_name"
                labelDescKey="days_until_due"
                fetchFirstPage={fetchPaymentTerms}
                initialData={selectedPaymentTerm ? [selectedPaymentTerm] : undefined}
                value={formData.payment_term || undefined}
                fetchFromUrl={({url}) => PAYMENT_TERMS_API.fetchPaymentTermsFromUrl({url})}
                onValueChange={() => {}}
                onItemsChange={(items) => {
                  const term = items[0] || null;
                  setSelectedPaymentTerm(term);
                  setFormData((prev) => ({...prev, payment_term: term?.base_uuid || undefined}));
                }}
                placeholder="Select payment terms"
                searchPlaceholder="Search payment terms..."
                emptyMessage="No payment terms found"
              />
            </div>

            {sourceType === "none" &&
              !customer &&
              currentInstitution.supports_multiple_currencies && (
                <div>
                  <Label htmlFor="invoice_currency" showOptional>
                    Invoice Currency
                  </Label>
                  <PaginatedSearchableSelect<Currency>
                    fetchFirstPage={(query) =>
                      CURRENCIES_API.fetchFirstPage({
                        ...query,
                        is_institution_supported: true,
                      })
                    }
                    fetchFromUrl={CURRENCIES_API.fetchFromUrl}
                    idKey="id"
                    valueKey="id"
                    labelKey="name"
                    labelDescKey="code"
                    value={documentCurrency?.id ?? null}
                    initialData={documentCurrency ? [documentCurrency] : []}
                    onValueChange={(values) => {
                      if (values.length === 0) {
                        setSelectedInvoiceCurrency(null);
                        setFormData((previous) => ({
                          ...previous,
                          exchange_rate: null,
                        }));
                        setLineItemsKey((key) => key + 1);
                      }
                    }}
                    onItemSelected={(currency) => {
                      setSelectedInvoiceCurrency(currency);
                      setFormData((previous) => ({
                        ...previous,
                        exchange_rate: null,
                      }));
                      setLineItemsKey((key) => key + 1);
                    }}
                    placeholder="Use institution base currency"
                    searchPlaceholder="Search supported currencies..."
                    emptyMessage="No supported currencies found"
                    description={`Defaults to ${
                      currentInstitution?.currency?.code ?? "the institution base currency"
                    } when left blank.`}
                  />
                </div>
              )}
          </FormSection>

          {isForeignCurrencyInvoice && documentCurrency && currentInstitution?.currency && (
            <FormSection
              title="Invoice Currency"
              description={`This invoice is recorded in ${documentCurrency.code}. Use the configured rate or provide a custom rate.`}
            >
              <ExchangeRateInput
                baseCurrency={currentInstitution.currency}
                transactionCurrency={documentCurrency}
                value={formData.exchange_rate ?? undefined}
                onChange={handleExchangeRateChange}
              />
            </FormSection>
          )}

          {/* Section 3: Line Items */}
          <div>
            <div>
              <LineItemsInput
                key={`${sourceType}-${lineItemsKey}`}
                model_name={
                  sourceType === "purchase_order"
                    ? "customer_purchase_order"
                    : sourceType === "quotation"
                      ? "quotation"
                      : "customer"
                }
                object_uuid={
                  purchaseOrder?.base_uuid ?? quotation?.base_uuid ?? customer?.base_uuid
                }
                currency={usesBaseCurrencyInput ? currentInstitution?.currency : documentCurrency}
                previewCurrency={usesBaseCurrencyInput ? documentCurrency : null}
                convertCataloguePricesTo={
                  !usesBaseCurrencyInput && isForeignCurrencyInvoice ? documentCurrency : null
                }
                exchangeRate={activeExchangeRate}
                initialItems={formData.line_items}
                showUOMSelector={true}
                allowUnitPriceOverride={true}
                calculateTaxOnUnitPrice={sourceType !== "recurring"}
                showTaxPricingDetails={true}
                showManufacturingOptions={true}
                onItemsChange={(items) =>
                  setFormData((prev) => ({
                    ...prev,
                    line_items: items.map((item) => ({
                      ...item,
                      type: "inventory" as const,
                      line_item: String(item.line_item),
                      item_name: item.item_name ?? "",
                      quantity_issued: item.quantity_issued ?? 0,
                      unit_of_measure: item.unit_of_measure?.toString() || "",
                    })),
                  }))
                }
              />
              {errors.line_items && (
                <p className="text-sm text-red-600 mt-2">{errors.line_items}</p>
              )}
            </div>
            {errors.line_items && <p className="text-sm text-red-600 mt-2">{errors.line_items}</p>}
          </div>

          <div className="space-y-2 lg:col-span-2">
            <Label htmlFor="description" showOptional className="text-base">
              Notes
            </Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) =>
                setFormData((prev) => ({...prev, description: e.target.value || undefined}))
              }
              placeholder="Enter any additional notes..."
              rows={4}
              className="w-full min-h-[120px] text-base resize-y"
            />
          </div>

          {/* Form Actions */}
          <div className="flex gap-3 pt-6">
            <SaveActionButton
              primaryLabel="Continue To Payment Status"
              pendingLabel="Creating..."
              isPending={isSubmitting}
              className="w-1/2"
              onAction={(action) => {
                void handleSubmit(undefined, action);
              }}
            />
          </div>
        </form>
      )}

      {/* Payment Status Modal */}
      <Dialog open={showPaymentModal} onOpenChange={setShowPaymentModal}>
        <DialogContent className="sm:max-w-[550px] max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Set Payment Status</DialogTitle>
            <DialogDescription>
              Specify the payment status for this invoice before finalizing.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-6 py-4 pr-2">
            {/* Total Amount Display */}
            <div className="p-4 bg-gradient-to-r from-primary/10 to-primary/5 rounded-lg border border-primary/20">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-muted-foreground">
                  Total Invoice Amount:
                </span>
                <span className="text-2xl font-bold text-primary">
                  {documentCurrency?.code} {formatCurrency(calculateTotal())}
                </span>
              </div>
            </div>

            {/* Payment Status Selection */}
            <div className="space-y-3">
              <Label required>Payment Status</Label>
              <RadioGroup
                value={paymentStatus}
                onValueChange={(value) => {
                  const status = value as PaymentStatus;
                  setPaymentStatus(status);
                  setPartialAmount("");
                  setPaymentErrors({});

                  if (status === "unpaid") {
                    setSelectedCashAccount(null);

                    setFormData((prev) => ({
                      ...prev,
                      cash_account: undefined,
                    }));
                  }
                }}
              >
                {/* Unpaid */}
                <div className="flex items-start space-x-3 p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
                  <RadioGroupItem value="unpaid" id="unpaid" className="mt-1" />
                  <Label htmlFor="unpaid" className="font-normal cursor-pointer flex-1">
                    <div>
                      <p className="font-semibold text-base">Unpaid</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        No payment has been received for this invoice
                      </p>
                    </div>
                  </Label>
                </div>

                {/* Fully Paid */}
                <div className="flex items-start space-x-3 p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
                  <RadioGroupItem value="paid" id="paid" className="mt-1" />
                  <Label htmlFor="paid" className="font-normal cursor-pointer flex-1">
                    <div>
                      <p className="font-semibold text-base">Fully Paid</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        Full payment of {documentCurrency?.code} {formatCurrency(calculateTotal())}{" "}
                        has been received
                      </p>
                    </div>
                  </Label>
                </div>

                {/* Partially Paid */}
                <div className="flex items-start space-x-3 p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer">
                  <RadioGroupItem value="partially_paid" id="partially_paid" className="mt-1" />
                  <Label htmlFor="partially_paid" className="font-normal cursor-pointer flex-1">
                    <div>
                      <p className="font-semibold text-base">Partially Paid</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        A partial payment has been received
                      </p>
                    </div>
                  </Label>
                </div>
              </RadioGroup>

              {/* Partial Amount Input */}
              {paymentStatus === "partially_paid" && (
                <div className="space-y-3 ml-8 p-4 bg-muted/30 rounded-lg border-primary">
                  <div>
                    <Label htmlFor="partial_amount" className="text-base" required>
                      Amount Paid
                    </Label>
                    <p className="text-xs text-muted-foreground mt-1 mb-2">
                      Enter the amount that has been paid so far
                    </p>
                  </div>
                  <FormattedNumberInput
                    id="partial_amount"
                    max={calculateTotal() - 0.01}
                    value={partialAmount}
                    onValueChange={(value) => {
                      setPartialAmount((value ?? 0).toString());
                      setPaymentErrors({});
                    }}
                    placeholder="0.00"
                    className="text-lg"
                  />
                  {paymentErrors.partialAmount && (
                    <p className="text-sm text-red-600 flex items-center gap-2">
                      <Icon icon="hugeicons:alert-circle" className="w-4 h-4" />
                      {paymentErrors.partialAmount}
                    </p>
                  )}
                  {partialAmount && !paymentErrors.partialAmount && (
                    <div className="pt-2 space-y-1">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Amount Paid:</span>
                        <span className="font-medium text-green-600">
                          {documentCurrency?.code}{" "}
                          {formatCurrency(parseFloat(partialAmount || "0"))}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Remaining Balance:</span>
                        <span className="font-semibold text-orange-600">
                          {documentCurrency?.code}{" "}
                          {formatCurrency(calculateTotal() - parseFloat(partialAmount || "0"))}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {paymentStatus !== "unpaid" && (
                <div className="space-y-3 p-4 bg-muted/30 rounded-lg border-primary">
                  <div>
                    <Label required>Cash Account</Label>
                  </div>

                  <CashAccountSelect
                    value={selectedCashAccount}
                    onChange={(account) => {
                      setSelectedCashAccount(account);
                      setFormData((prev) => ({
                        ...prev,
                        cash_account: account
                          ? {
                              content_type: account.model.id,
                              content_object_uuid: account.base_uuid,
                            }
                          : undefined,
                      }));
                    }}
                    placeholder="Select cash account"
                    description="Choose the cash, bank, mobile money or wallet account where the deposit is
                      received."
                  />

                  {paymentErrors.cash_account && (
                    <p className="text-sm text-red-600 flex items-center gap-2">
                      <Icon icon="hugeicons:alert-circle" className="w-4 h-4" />
                      {paymentErrors.cash_account}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="gap-2 pt-4">
            <Button
              type="button"
              onClick={handleFinalSubmit}
              disabled={isSubmitting}
              className="w-full rounded-full"
            >
              {isSubmitting ? (
                <>
                  <Icon icon="svg-spinners:180-ring" className="w-4 h-4 mr-2" />
                  Creating...
                </>
              ) : (
                "Create Invoice"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CreateCustomerPanel
        open={showCreateCustomer}
        onClose={() => setShowCreateCustomer(false)}
        onCreated={(id, name, newCustomer) => {
          setCustomer(newCustomer);
          setSelectedCustomer(newCustomer);
          setPreselectedCustomerLabel(name);
          setShowCreateCustomer(false);
        }}
      />
    </PageLayout>
  );
}
