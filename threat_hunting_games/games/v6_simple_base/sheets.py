import string, json
import numpy as np

class Matrix:

    def __init__(self):
        self._rows = {}
        self._col_keys = set()

    def row(self, row_key):
        if row_key not in self._rows:
            row = self._rows[row_key] = {}
            for col_key in self._col_keys:
                row[col_key] = 0
        return self._rows[row_key]

    def col(self, col_key):
        if col_key not in self._col_keys:
            self._col_keys.add(col_key)
            for row in self._rows.values():
                row[col_key] = 0
        col = {}
        for row_key, val in self._rows.items():
            col[row_key] = val
        return col

    def row_keys(self):
        return sorted(self._rows)

    def col_keys(self):
        return sorted(self._col_keys)

    def row_labels(self):
        labels = []
        for policy, action_picker in self.row_keys():
            label = policy
            if action_picker:
                label = '-'.join([label, action_picker])
        return tuple(labels)

    def col_labels(self):
        labels = []
        for policy, action_picker in self.col_keys():
            label = policy
            if action_picker:
                label = '-'.join([label, action_picker])
        return tuple(labels)

    def num_rows(self):
        return len(self._rows)

    def num_cols(self):
        return len(self._col_keys)

    def as_matrix(self):
        rows = []
        col_keys = sorted(self._col_keys)
        col_names = ['']
        col_names.extend(self.col_name(x) for x in col_keys)
        rows.append(col_names)
        for row_key in self.row_keys():
            row = [self.row_name(row_key)]
            for col_key in self.col_keys():
                row.append(self._rows[row_key][col_key])
            rows.append(row)
        return rows

    def as_unlabeled_matrix(self):
        rows = []
        col_keys = sorted(self._col_keys)
        for row_key in self.row_keys():
            row = []
            for col_key in self.col_keys():
                row.append(self._rows[row_key][col_key])
            rows.append(row)
        return rows

    def as_tensor(self):
        return np.array(self.as_unlabeled_matrix())

    def cols(self):
        cols = {}
        for col_key in self._col_keys:
            cols[col_key] = self.col(col_key)
        return cols

    def inc_val(self, row_key, col_key, incr):
        # make sure row/col exist
        row = self.row(row_key)
        self.col(col_key)
        self._rows[row_key][col_key] += incr
        return self._rows[row_key][col_key]

    def set_val(self, row_key, col_key, val):
        # make sure row/col exist
        row = self.row(row_key)
        self.col(col_key)
        self._rows[row_key][col_key] = val
        return val

    def val(self, row_key, col_key):
        # make sure row/col exist
        row = self.row(row_key)
        self.col(col_key)
        return self._rows[row_key][col_key]

    def contains_row(self, row_key):
        return row_key in self._rows

    def contains_col(self, col_key):
        return col_key in self._col_keys

    def row_name(self, row_key):
        assert row_key in self._rows, f"unknown row: {row_key}"
        name = row_key
        if not isinstance(name, str):
            name = '-'.join(x for x in name if x)
        return name

    def col_name(self, col_key):
        assert col_key in self._rows, f"unknown col: {col_key}"
        name = col_key
        if not isinstance(name, str):
            name = '-'.join(x for x in name if x)
        return name

    def __getitem__(self, row_key):
        return self._rows[row_key]


class Sheet:

    def __init__(self, key, json_preamble=None, csv_preamble=None):
        self._key = key
        self._json_preamble = json_preamble
        self._csv_preamble = csv_preamble
        self._atk_matrix = Matrix()
        self._def_matrix = Matrix()
        self._rows = {}
        self._col_keys = set()

    @property
    def json_preamble(self):
        return self._json_preamble

    @property
    def csv_preamble(self):
        return self._csv_preamble

    @property
    def atk_matrix(self):
        return self._atk_matrix

    @property
    def def_matrix(self):
        return self._def_matrix

    @property
    def def_policies(self):
        return self.def_matrix.row_keys()

    @property
    def atk_policies(self):
        return self.atk_matrix.col_keys()

    @property
    def num_rows(self):
        return len(self.def_policies)

    @property
    def num_cols(self):
        return len(self.atk_policies)

    @property
    def key(self):
        return self._key

    @property
    def name(self):
        name = self._key
        if not isinstance(name, str):
            name = '-'.join(name)
        return name

    def as_tensor(self):
        t = np.stack([
            self.atk_matrix.as_tensor(),
            self.def_matrix.as_tensor()])
        return t

    def dump_json(self, fh):
        data = {}
        if self._json_preamble:
            data.update(self._json_preamble)
        data["attacker_rows"] = self.atk_matrix.col_labels()
        data["defender_rows"] = self.def_matrix.row_labels()
        data["attacker_matrix"] = self.atk_matrix.as_unlabeled_matrix()
        data["defender_matrix"] = self.def_matrix.as_unlabeled_matrix()
        json.dump(data, fh, indent=2)

    def dump_csv(self, writer):
        # note: does not save the csv file
        if self._csv_preamble:
            for row in self._csv_preamble:
                writer.writerow(row)
            # blank row
            writer.writerow([])
        for row in self.atk_matrix.as_matrix():
            writer.writerow(row)
        # blank row
        for row in self.def_matrix.as_matrix():
            writer.writerow(row)

    def dump_xlsx(self, xls_sheet):
        # note: does not save the workbook
        xl_cols = string.ascii_uppercase
        def _col_idx(int_idx):
            quotient, remainder = divmod(int_idx, len(xl_cols))
            letter = xl_cols[remainder]
            if quotient:
                letter = letter * (quotient + 1)
            return letter
        def _cell_name(row_idx, col_idx):
            col_letter = _col_idx(col_idx)
            cell_name = f"{col_letter}{row_idx}"
            return cell_name
        row_idx = 1
        if self._csv_preamble:
            for row in self._csv_preamble:
                for i, val in enumerate(row):
                    cell_name = _cell_name(row_idx, i)
                    xls_sheet[cell_name] = val
                row_idx += 1
            row_idx += 1 # blank row
        xls_sheet[_cell_name(row_idx, 0)] = "Attacker Matrix"
        row_idx += 1 # blank row
        for row in self.atk_matrix.as_matrix():
            for i, val in enumerate(row):
                cell_name = _cell_name(row_idx, i)
                xls_sheet[cell_name] = val
            row_idx += 1
        row_idx += 1 # blank row
        xls_sheet[_cell_name(row_idx, 0)] = "Defender Matrix"
        row_idx += 1 # blank_row
        for row in self.def_matrix.as_matrix():
            for i, val in enumerate(row):
                cell_name = _cell_name(row_idx, i)
                xls_sheet[cell_name] = val
            row_idx += 1

    def __key__(self):
        return self._key


class Sheets:

    def __init__(self):
        self._sheets = {}

    def sheet(self, sheet_key):
        if sheet_key not in self._sheets:
            self._sheets[sheet_key] = Sheet(sheet_key)
        return self._sheets[sheet_key]

    def sheet_names(self):
        return sorted(self._sheets)

    def sheets(self):
        sheets = []
        for name in self.sheet_names():
            sheets.append(self._sheets[name])
        return sheets

    def __contains__(self, sheet_key):
        return sheet_key in self._sheets
