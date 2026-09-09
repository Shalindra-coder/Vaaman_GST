__version__ = "0.0.1"


def _patch_purchase_reconciliation_excel():
	try:
		from vaaman_gst.overrides.purchase_reconciliation_tool import patch_build_excel

		patch_build_excel()
	except ImportError:
		# india_compliance not installed on this bench — Purchase Reconciliation Excel patch skipped
		pass


_patch_purchase_reconciliation_excel()



