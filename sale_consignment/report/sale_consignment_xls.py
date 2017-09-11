from . import abstract_report_xlsx
from openerp.report import report_sxw
from openerp import _

class sale_consignment_report(abstract_report_xlsx.AbstractReportXslx):
    def __init__(self, name, table, rml=False, parser=False, header=True,
                 store=False):
        super(sale_consignment_report, self).__init__(
            name, table, rml, parser, header, store)

    def _get_report_name(self):
        return _('Sale Consignment Report')

    def _get_report_columns(self, report):
        return {
            0: {'header': _('Product Reference'),'field': 'product_reference','width': 25},
            1: {'header': _('Barcode'),'field': 'product_barcode','width': 15},
            2: {'header': _('Product Name'),'field': 'product_name','width': 60},
            3: {'header': _('Product Attribute Name'),'field': 'product_attribute_value','width': 35},
            4: {'header': _('Qty Purchased'),'field': 'qty_in', 'type': 'amount', 'width': 15, 'compute_subtotal': True,},
            5: {'header': _('Qty Sold'),'field': 'qty_out', 'type': 'amount', 'width': 15, 'compute_subtotal': True,},
            6: {'header': _('Qty Returned(Purchase)'),'field': 'qty_return_out', 'type': 'amount', 'width': 15, 'compute_subtotal': True,},
            7: {'header': _('Qty Returned(Sale)'),'field': 'qty_return_in', 'type': 'amount', 'width': 15, 'compute_subtotal': True,},
            8: {'header': _('Qty Adjustment(IN)'),'field': 'qty_adj_in', 'type': 'amount', 'width': 15, 'compute_subtotal': True,},
            9: {'header': _('Qty Adjustment(OUT)'),'field': 'qty_adj_out', 'type': 'amount', 'width': 15, 'compute_subtotal': True,},
        }

    def _get_report_filters(self, report):
        return [
            [_('Date range filter'),
                _('From: %s To: %s') % (report.date_from, report.date_to)],
        ]

    def _get_col_count_filter_name(self):
        return 2

    def _get_col_count_filter_value(self):
        return 2

    def _get_col_count_final_balance_name(self):
        return 3

    def _get_col_pos_final_balance_label(self):
        return 3

    def _generate_report_content(self, workbook, report):
        for sale_history_brand in report.sale_history_brands:
            self.write_array_title(sale_history_brand.product_brand_id.name)
            self.write_array_header()

            for line in sale_history_brand.sale_history_products:
                self.write_line(line)

            name = sale_history_brand.product_brand_id.name
            label = _('Total')
            self.write_ending_balance(sale_history_brand.sale_history_products, name, label)
            self.row_pos += 1

sale_consignment_report(
    'report.sale_consignment.sale_consignment_history_xls',
    'sale.consignment.history',
    parser=report_sxw.rml_parse
)