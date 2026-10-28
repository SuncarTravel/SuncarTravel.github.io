"""Build the public-domain OurAirports IATA catalogue from a downloaded CSV."""
import csv
import datetime
import json
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[1]
records = {}
with open(sys.argv[1], encoding='utf-8-sig', newline='') as source:
    for row in csv.DictReader(source):
        code = row['iata_code'].strip().upper()
        if not re.fullmatch('[A-Z]{3}', code) or row['type'] == 'closed':
            continue
        rank = (row['scheduled_service'] == 'yes', row['type'] == 'large_airport', row['type'] == 'medium_airport')
        item = [code, row['name'], row['municipality'], row['iso_country'], row['keywords'], row['scheduled_service'] == 'yes']
        if code not in records or rank > records[code][0]:
            records[code] = (rank, item)
data = {'source': 'https://ourairports.com/data/', 'license': 'Public domain',
        'updated': datetime.date.today().isoformat(),
        'airports': [records[key][1] for key in sorted(records)]}
target = root / 'assets' / 'airports-iata.json'
target.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
print(f'{len(records)} IATA codes; {target.stat().st_size} bytes')
