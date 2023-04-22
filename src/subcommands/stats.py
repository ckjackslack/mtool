import csv
import statistics


def get_csv_rows(filepath):
    with open(filepath) as f:
        reader = csv.DictReader(f)
        return [row for row in reader], reader.fieldnames


def show_stats(filepath, column):
    rows, columns = get_csv_rows(filepath)
    print(f"Shape: {len(rows)}x{len(columns)} matrix")
    if column in columns:
        print(f"Target column: {column}")
        vals = [int(r.get(column)) for r in rows]
        print("Average:", statistics.mean(vals))
        print("Max:", max(vals))
        print("Min:", min(vals))