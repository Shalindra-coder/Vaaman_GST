# Copyright (c) 2026, Shalindra Aporiya and contributors
# For license information, please see license.txt

# import frappe

import frappe
from frappe import _

from erpnext.accounts.report.tax_withholding_details.tax_withholding_details import (
	get_result,
	get_tds_docs,
)
from erpnext.accounts.utils import get_fiscal_year


def execute(filters=None):
	if filters.get("party_type") == "Customer":
		party_naming_by = frappe.db.get_single_value("Selling Settings", "cust_master_name")
	else:
		party_naming_by = frappe.db.get_single_value("Buying Settings", "supp_master_name")

	filters.update({"naming_series": party_naming_by})

	validate_filters(filters)

	columns = get_columns(filters)
	(
		tds_docs,
		tds_accounts,
		tax_category_map,
		journal_entry_party_map,
		invoice_total_map,
	) = get_tds_docs(filters)

	res = get_result(
		filters, tds_docs, tds_accounts, tax_category_map, journal_entry_party_map, invoice_total_map
	)
    
	je_data = get_je_details(filters)
    
	final_result = group_by_party_and_category(res, filters, je_data)

	return columns, final_result


def validate_filters(filters):
	"""Validate if dates are properly set and lie in the same fiscal year"""
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))

	from_year = get_fiscal_year(filters.from_date)[0]
	to_year = get_fiscal_year(filters.to_date)[0]
	if from_year != to_year:
		frappe.throw(_("From Date and To Date lie in different Fiscal Year"))

	filters["fiscal_year"] = from_year


def get_je_details(filters):
	return frappe.db.sql("""
		SELECT 
			jea.party,
			jea.account as je_account,
			SUM(jea.debit_in_account_currency) as je_debit,
			SUM(jea.credit_in_account_currency) as je_credit
		FROM `tabJournal Entry Account` jea
		INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
		WHERE je.docstatus = 1
			AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND jea.account LIKE '%%TDS-Payable%%'
			AND jea.party_type = %(party_type)s
		GROUP BY jea.party, jea.account
	""", {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"party_type": filters.party_type
	}, as_dict=1)


def group_by_party_and_category(data, filters, je_data=None):
	party_category_wise_map = {}

	for row in data:
		key = (row.get("party"), row.get("section_code"))
		party_category_wise_map.setdefault(
			key,
			{
				"pan": row.get("pan"),
				"tax_id": row.get("tax_id"),
				"party": row.get("party"),
				"party_name": row.get("party_name"),
				"section_code": row.get("section_code"),
				"entity_type": row.get("entity_type"),
				"rate": row.get("rate"),
				"total_amount": 0.0,
				"tax_amount": 0.0,
				"je_account": "",
				"je_debit": 0.0,
				"je_credit": 0.0
			},
		)

		party_category_wise_map[key]["total_amount"] += row.get("total_amount", 0.0)
		party_category_wise_map[key]["tax_amount"] += row.get("tax_amount", 0.0)

	if je_data:
		for je in je_data:
			for key, val in party_category_wise_map.items():
				if key[0] == je.party:
					val["je_account"] = je.je_account
					val["je_debit"] += je.je_debit
					val["je_credit"] += je.je_credit

	final_result = get_final_result(party_category_wise_map)
	return final_result


def get_final_result(party_category_wise_map):
	out = []
	for _key, value in party_category_wise_map.items():
		out.append(value)
	return out


def get_columns(filters):
	pan = "pan" if frappe.db.has_column(filters.party_type, "pan") else "tax_id"
	columns = [
		{"label": _(frappe.unscrub(pan)), "fieldname": pan, "fieldtype": "Data", "width": 90},
		{
			"label": _(filters.get("party_type")),
			"fieldname": "party",
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 180,
		},
	]

	if filters.naming_series == "Naming Series":
		columns.append(
			{
				"label": _(filters.party_type + " Name"),
				"fieldname": "party_name",
				"fieldtype": "Data",
				"width": 180,
			}
		)

	columns.extend(
		[
			{
				"label": _("Section Code"),
				"options": "Tax Withholding Category",
				"fieldname": "section_code",
				"fieldtype": "Link",
				"width": 180,
			},
			{"label": _("Entity Type"), "fieldname": "entity_type", "fieldtype": "Data", "width": 180},
			{
				"label": _("TDS Rate %") if filters.get("party_type") == "Supplier" else _("TCS Rate %"),
				"fieldname": "rate",
				"fieldtype": "Percent",
				"width": 120,
			},
			{
				"label": _("Total Amount"),
				"fieldname": "total_amount",
				"fieldtype": "Float",
				"width": 120,
			},
			{
				"label": _("Tax Amount"),
				"fieldname": "tax_amount",
				"fieldtype": "Float",
				"width": 120,
			},
			{
				"label": _("Journal Entry Account"),
				"fieldname": "je_account",
				"fieldtype": "Link",
				"options": "Account",
				"width": 180,
			},
			{
				"label": _("Debit"),
				"fieldname": "je_debit",
				"fieldtype": "Currency",
				"width": 120,
			},
			{
				"label": _("Credit"),
				"fieldname": "je_credit",
				"fieldtype": "Currency",
				"width": 120,
			},
		]
	)

	return columns