import {IFeature} from "#/_types/api.types";

export const FEATURE_REGISTRY: IFeature[] = [
  {
    label: "Sales Orders",
    keywords: ["sales orders", "SO", "create order", "view SO details", "customer purchase order"],
    url: "/purchase-orders/",
  },
  {
    label: "Outgoing Orders",
    keywords: [
      "purchase orders",
      "create order",
      "view purchase order details",
      "outgoing purchase order",
      "vendor purchase order",
    ],
    url: "/vendor-purchase-orders/",
  },
  {
    label: "Requisitions",
    keywords: ["requisition", "create requisition", "view requisition details"],
    url: "/requisitions/",
  },
  {
    label: "Requisition Types",
    keywords: ["requisition types", "create requisition type", "view requisition types"],
    url: "/requisitions/?tab=types",
  },
  {
    label: "Admin",
    keywords: ["admin", "administration", "admin panel"],
    url: "/admin/",
  },
  {
    label: "Staff Roles",
    keywords: ["staff roles", "manage roles", "user roles"],
    url: "/users/roles/",
  },

  {
    label: "Staff",
    keywords: ["staff", "all staff", "institution staff"],
    url: "/users/",
  },

  {
    label: "Customers Management",
    keywords: ["customers", "manage customers", "customer details"],
    url: "/customers/",
  },
  {
    label: "Quotation Management",
    keywords: ["quotations", "manage quotations", "quotation details"],
    url: "/quotations/",
  },

  {
    label: "Invoice Management",
    keywords: ["invoice", "invoice management", "invoice details", "create invoice"],
    url: "/invoices/",
  },
  {
    label: "Customer/Invoice Payments",
    keywords: ["customer payments", "deposits", "invoice payments"],
    url: "/customer-payments",
  },

  {
    label: "Inventory Management",
    keywords: ["inventory", "inventory items", "add inventory"],
    url: "/inventory-items/",
  },
  {
    label: "Branch Inventory Management",
    keywords: ["branch inventory", "inventory items", "add inventory"],
    url: "/branch-inventory-items/",
  },

  {
    label: "Fixed Asset Management",
    keywords: ["fixed assets", "assets"],
    url: "/fixed-asset-items/",
  },

  {
    label: "Transaction Management",
    keywords: ["transactions", "transaction details", "general journal", "journal entries"],
    url: "/transactions/",
  },

  {
    label: "Chart of Accounts",
    keywords: ["accounts", "accounts management", "accountant"],
    url: "/accounts/",
  },
  {
    label: "Bank Accounts Management",
    keywords: ["accounts", "accounts management", "banks", "bank accounts"],
    url: "/banks/",
  },
  {
    label: "Institution Settings",
    keywords: ["settings", "change settings"],
    url: "/settings/",
  },

  {
    label: "Branch Management",
    keywords: ["branches", "institution branches"],
    url: "/branches/",
  },
  {
    label: "Fiscal Years",
    keywords: ["fiscal year", "set fiscal year"],
    url: "/fiscal-calendar/?tab=years/",
  },
  {
    label: "Transaction Posting Periods",
    keywords: ["transaction posting period", "set transaction posting period"],
    url: "/fiscal-calendar/?tab=periods",
  },

  {
    label: "Approval Management",
    keywords: ["manage approvals", "approvals"],
    url: "/approvals/",
  },
  {
    label: "Payment Terms",
    keywords: ["manage payment terms", "payment terms"],
    url: "/payment-terms/",
  },

  {
    label: "Inventory Item Categories",
    keywords: ["item categories", "inventory categories", "inventory"],
    url: "/item-categories/",
  },

  {
    label: "Units of Measure",
    keywords: ["measurent units", "units", "measure", "units of measure"],
    url: "/unit-of-measurement/",
  },

  {
    label: "Sales Persons",
    keywords: ["sales person", "sales", "commission"],
    url: "/sales-person/",
  },

  {
    label: "Asset Categories",
    keywords: ["assets", "asset category", "categories"],
    url: "/asset-categories/",
  },

  {
    label: "Tax Management",
    keywords: ["taxes", "tax management", "manage taxes", "tax rules", "tax types"],
    url: "/taxes/",
  },

  {
    label: "Profile Management",
    keywords: ["profile management", "manage profiles", "user profiles", "change password"],
    url: "/user-setting/",
  },
  {
    label: "Credit Notes",
    keywords: ["credit", "notes", "credit notes"],
    url: "/credit-notes",
  },
  {
    label: "Debit Notes",
    keywords: ["debit", "notes", "debit notes"],
    url: "/debit-notes",
  },
  {
    label: "Stock Transfers",
    keywords: [
      "stock",
      "transfers",
      "stock management",
      "transfers",
      "allocation",
      "branch allocation",
    ],
    url: "/admin/branch-allocation/",
  },
  {
    label: "Cash book",
    keywords: ["cash", "book", "imprest"],
    url: "/cashbooks/",
  },
  {
    label: "Balance Sheet",
    keywords: ["balance sheet", "financial statement"],
    url: "/reports/balance-sheet/",
  },
  {
    label: "Income Statement",
    keywords: ["income statement", "financial statement"],
    url: "/reports/income-statement/",
  },
  {
    label: "Trial Balance",
    keywords: ["trial balance", "financial statement"],
    url: "/reports/trial-balance/",
  },

  {
    label: "Cashflow Statement",
    keywords: ["cashflow", "cash flow", "financial statement", "cash statement"],
    url: "/reports/cash-flow/",
  },
  {
    label: "Other Income",
    keywords: ["other income", "other", "income"],
    url: "/other-income/",
  },
  {
    label: "Return Reasons",
    keywords: ["return reasons"],
    url: "/admin/return-reasons/",
  },
  {
    label: "Asset Classes",
    keywords: ["asset classes"],
    url: "/asset-class/",
  },
  {
    label: "Asset Disposal",
    keywords: ["asset disposal", "disposing"],
    url: "/asset-disposal/",
  },
  {
    label: "Disposed Assets",
    keywords: ["disposed assets", "disposed"],
    url: "/disposed-assets/",
  },
  {
    label: "Tax returns",
    keywords: ["tax returns", "filed taxes"],
    url: "/tax-returns/",
  },
  {
    label: "Tax Payments",
    keywords: ["tax payments"],
    url: "/tax-payments/",
  },
];
