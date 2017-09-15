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

		sheet = workbook.add_worksheet('Stock Info')
		format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
		format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
		format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True})
		format3 = workbook.add_format({'bottom': True, 'top': True, 'font_size': 12})
		format99 = workbook.add_format({'font_size': 10, 'align': 'center',})
		font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 10,'bold':True})
		red_mark = workbook.add_format({'font_size': 10,
		                                'font_color': 'red'})

		red_mark_amount = workbook.add_format({'font_size': 10,
		                                'font_color': 'red'})
		justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})

		invoice_header =  workbook.add_format({'font_size': 10, 'align': 'left',})
		invoice_header_mark = workbook.add_format({'font_size': 10, 'align': 'left','font_color':'red'})

		style_tot = workbook.add_format({'font_size': 10,'bold':True})
		amount_style = workbook.add_format({'font_size': 10,'align':'right'})
		style_tot.set_align('right')
		red_mark_amount.set_align('right')
		format3.set_align('center')
		font_size_8.set_align('center')
		justify.set_align('justify')
		format1.set_align('center')
		red_mark.set_align('center')

		

		# sheet.write(1,0,'PT Social Bella Indonesia',format99)
		sheet.merge_range('A2:F2','PT Social Bella Indonesia',format1)
		sheet.write(3,0,'Cut Off Date',format99)
		sheet.write(4,0,'Filter',format99)

		if get_report_type[0] == 'receivable':
			sheet.merge_range('A3:F3','AR Monitoring Report',format1)
		else:
			sheet.merge_range('A3:F3','AP Monitoring Report',format1)

		for i in get_report_type[1]:
			sheet.write(3,0,'Cut Off Date',format99)
			sheet.write(3,1,i,format99)

		for i in get_report_type[2]:
			sheet.write(4,0,'Filter',format99)
			sheet.write(4,1,i,format99)
		
		partner_col = 0

		detail_row = 9
		detail_col = 0

		

		total_partner	= len(get_partner)
		for partner_count in range(0,total_partner):
			partner_idx 	= get_partner[partner_count]
			get_lines 		= self.get_lines(data, partner_idx)
			amount_total	= 0

			partner_id = self.env['res.partner'].search([('id','=',partner_idx)])

			concat_partner = str(partner_id.name) + " " + "(TOP" +" " + str(partner_id.property_payment_term_id.name) + ")" or str(partner_id.name) +" " + "(TOP" +" "  + str(partner_id.property_supplier_payment_term_id.name+")")

			sheet.write(detail_row,detail_col,str(concat_partner),font_size_8) # Detail Partner 
			detail_row +=1

			sheet.write(detail_row,detail_col+0,'Invoice',font_size_8)
			sheet.write(detail_row,detail_col+1,'Invoice Date',font_size_8)
			sheet.write(detail_row,detail_col+2,'Due Date',font_size_8)
			sheet.write(detail_row,detail_col+3,'Aging(Days)',font_size_8)
			sheet.write(detail_row,detail_col+4,'Currency',font_size_8)
			sheet.write(detail_row,detail_col+5,'Amount',font_size_8)

			
			detail_row +=1
			for i in get_lines:
				sheet.write(detail_row,detail_col,i['invoice_name'],invoice_header if i['aging_day'] < 0 else invoice_header_mark)
				sheet.write(detail_row,detail_col+1,i['invoice_date'],invoice_header if i['aging_day'] < 0 else invoice_header_mark)
				sheet.write(detail_row,detail_col+2,i['due_date'],invoice_header if i['aging_day'] < 0 else invoice_header_mark)
				sheet.write(detail_row,detail_col+3,i['aging_day'],format99 if i['aging_day'] < 0 else red_mark)
				sheet.write(detail_row,detail_col+4,i['currency'],format99 if i['aging_day'] < 0 else red_mark)
				sheet.write(detail_row,detail_col+5,i['amount'],amount_style if i['aging_day'] < 0 else red_mark_amount)
				amount_total += (i['amount'])

				detail_row += 1

			if get_lines:
				sheet.write(detail_row,detail_col,"TOTAL",style_tot)
				sheet.write(detail_row,detail_col+5,amount_total,style_tot)
				detail_row += 2
			
				
#



ar_ap_monitoring_xls('report.monitoring_report.monitoring_report_xls.xlsx', 'account.invoice')