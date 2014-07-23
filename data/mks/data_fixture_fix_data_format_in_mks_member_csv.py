__author__ = 'TOSHIBA'

from csv import DictReader, DictWriter
import time
from pprint import pprint

LIST_OF_UNFOUND_BLOG_IDS = [
    '5',
    '42',
    '18',

]

csv_file = open('data_from_json_mks.member.csv', mode='r')
csv_reader = DictReader(csv_file)
csv_list = [row for row in csv_reader]
csv_file_output = open('data_from_json_mks.member.csv', mode='wb')

fixed_csv_list = list()
for row in csv_list:
    new_row = dict()
    for key, value in row.items():
        new_value = value
        if key == 'date_of_birth' or key == 'end_date' or key == 'start_date' or key == 'date_of_death':
            if value != 'None':
                print key
                print value, type(value)
                try:
                    time_value = time.strptime(value, '%d/%m/%Y')
                    time_value_fixed = time.strftime('%Y-%m-%d', time_value)
                except ValueError:
                    print 'here'
                    time_value_fixed = value
                print time_value_fixed
                new_value = time_value_fixed
        new_row[key] = new_value

        if key == 'user':
            print value
            new_value = 'None'
        new_row[key] = new_value

        if key == 'blog' and str(value) in LIST_OF_UNFOUND_BLOG_IDS:
            new_value = 'None'

        new_row[key] = new_value

    fixed_csv_list.append(new_row)
pprint(fixed_csv_list[0])
fieldnames = [key for key, value in csv_list[0].items()]
print fieldnames
csv_writer = DictWriter(csv_file_output, fieldnames=fieldnames)
csv_writer.writeheader()
csv_writer.writerows(fixed_csv_list)

csv_file_output.close()


