# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2017-TODAY Cybrosys Technologies(<http://www.cybrosys.com>).
#    Author: Jesni Banu(<https://www.cybrosys.com>)
#    you can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    GENERAL PUBLIC LICENSE (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from datetime import date, datetime, timedelta
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT
import locale


class ar_ap_monitoring_xls(ReportXlsx):

	
	def get_report_type(self,data):
		if data.get('form', False) and data['form'].get('report_type', False):
			report_type = []
			cut_off_date = []
			filter_report = []
			report_type_val = data['form']['report_type']
			cut_off_date_val = data['form']['cut_off_date']
			filter_report_val = data['form']['filter_report']

			report_type.append(report_type_val)
			cut_off_date.append(cut_off_date_val)
			filter_report.append(filter_report_val)
		return report_type,cut_off_date,filter_report



	def get_partner(self,data):
		if data.get('form', False) and data['form'].get('filter_partner', False):
			partner_id = []
			obj = self.env['res.partner'].search([('id', 'in', data['form']['filter_partner'])])
			for j in obj:
				partner_id.append(j.id)
		return partner_id


	def get_lines(self,data,partner):
		lines = []
		cut_off_date_val = data['form']['cut_off_date']
		filter_report_val = data['form']['filter_report']
		total_all = 0.0


		if filter_report_val == 'overdue':
			invoice_history = self.env['account.invoice'].search([('partner_id', '=', partner),
																	('state','=','open'),
																	('date_due','<',cut_off_date_val)])
		else:
			invoice_history = self.env['account.invoice'].search([('partner_id', '=', partner),
																	('state','=','open')])

			

		for x in invoice_history:
			total_all += x.amount_total
			fmt = '%Y-%m-%d'
			cut_off_date_formatted = datetime.strptime(cut_off_date_val, fmt)
			date_due_formatted =  datetime.strptime(x.date_due,fmt)
			diff_date = int(str((cut_off_date_formatted-date_due_formatted).days))

			amount_obj = x.residual

	

			vals = {
				'partner_name'	: x.partner_id.name,
				'invoice_name'  : x.number,
				'invoice_date'  : x.date_invoice,
				'due_date'		: x.date_due,
				'aging_day'		: diff_date,
				'currency'		: x.currency_id.name,
				'amount'		: x.residual,
				'amount_total'  : total_all,
			}
			lines.append(vals)

		sorting_lines = sorted(lines, key=lambda k: k['aging_day'], reverse=True) 

		return sorting_lines





	def generate_xlsx_report(self, workbook, data, lines):
		get_report_type = self.get_report_type(data)
		get_partner = self.get_partner(data)

		sheet = workbook.add_worksheet('Monitoring %s' % ('AR' if get_report_type[0] == 'receivable' else 'AP'))
		title = workbook.add_format({'font_size': 12, 'align': 'center', 'bold': True})

		group_header = workbook.add_format({'font_size': 10,'bold':True, 'align': 'left'})
		header = workbook.add_format({'font_size': 10,'bold':True, 'align': 'center', 'bottom': True, 'right': True, 'left': True, 'top': True})
		
		normal = workbook.add_format({'font_size': 10, 'align': 'left','right': True, 'left': True})
		normal_redmark = workbook.add_format({'font_size': 10, 'align': 'left','font_color':'red','right': True, 'left': True})

		normal_amount = workbook.add_format({'font_size': 10, 'align': 'right','right': True, 'left': True})
		normal_amount_redmark = workbook.add_format({'font_size': 10, 'align': 'right','font_color':'red','right': True, 'left': True})

		group_footer = workbook.add_format({'font_size': 10,'bold':True, 'align': 'right', 'bottom': True, 'right': True, 'left': True, 'top': True})
		group_footer_amount = workbook.add_format({'font_size': 10,'bold':True, 'align': 'right', 'bottom': True, 'right': True, 'left': True, 'top': True})

		normal_amount.set_num_format('#,##0.00')
		normal_amount_redmark.set_num_format('#,##0.00')
		group_footer_amount.set_num_format('#,##0.00')

		for i in range(0, 6):
			sheet.set_column(i, i, 15)

		sheet.merge_range('A1:F1',self.env.user.company_id.name,title)
		sheet.merge_range('A2:F2','%s Monitoring Report' %  ('AR' if get_report_type[0] == 'receivable' else 'AP'),title)

		for i in get_report_type[1]:
			sheet.write_string(3,0,'Cut Off Date')
			sheet.write_string(3,1,i)

		for i in get_report_type[2]:
			sheet.write_string(4,0,'Filter')
			sheet.write_string(4,1,i)
		
		detail_row = 6
		detail_col = 0

		total_partner = len(get_partner)
		for partner_count in range(0,total_partner):
			partner_idx = get_partner[partner_count]
			get_lines = self.get_lines(data, partner_idx)
			amount_total = 0

			if get_lines:
				partner_id = self.env['res.partner'].search([('id','=',partner_idx)])
				concat_partner = "%s (TOP %s)" % (partner_id.name, partner_id.property_payment_term_id.name or partner_id.property_supplier_payment_term_id.name) 

				sheet.merge_range(detail_row,0, detail_row, 5, str(concat_partner),group_header)
				detail_row +=1

				sheet.write(detail_row,detail_col+0,'Invoice',header)
				sheet.write(detail_row,detail_col+1,'Invoice Date',header)
				sheet.write(detail_row,detail_col+2,'Due Date',header)
				sheet.write(detail_row,detail_col+3,'Aging(Days)',header)
				sheet.write(detail_row,detail_col+4,'Currency',header)
				sheet.write(detail_row,detail_col+5,'Amount',header)

				
				detail_row +=1
				for i in get_lines:
					sheet.write(detail_row,detail_col,i['invoice_name'],normal if i['aging_day'] < 0 else normal_redmark)
					sheet.write(detail_row,detail_col+1,i['invoice_date'],normal if i['aging_day'] < 0 else normal_redmark)
					sheet.write(detail_row,detail_col+2,i['due_date'],normal if i['aging_day'] < 0 else normal_redmark)
					sheet.write_number(detail_row, detail_col+3, float(i['aging_day']), normal_amount if i['aging_day'] < 0 else normal_amount_redmark)
					sheet.write(detail_row,detail_col+4,i['currency'],normal if i['aging_day'] < 0 else normal_redmark)
					sheet.write_number(detail_row, detail_col+5, float(i['amount']), normal_amount if i['aging_day'] < 0 else normal_amount_redmark)
					amount_total += (i['amount'])

					detail_row += 1

				sheet.merge_range(detail_row, 0, detail_row, 4, "TOTAL", group_footer)
				sheet.write_number(detail_row, 5, float(amount_total), group_footer_amount)
				detail_row += 2

ar_ap_monitoring_xls('report.monitoring_report.monitoring_report_xls.xlsx', 'account.invoice')