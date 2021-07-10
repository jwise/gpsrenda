import fitparse
import datetime
import sys

class Interpolator:
    def __init__(self, field, flatten_zeroes = None):
        self.field = field
        self.flatten_zeroes = flatten_zeroes
        self.p = 0

    def value(self, time):
        if self.field is None:
            return None

        if time < self.field[0][0]:
            return None
        if time > self.field[-1][0]:
            return None

        # do we have to rewind?
        if time < self.field[self.p][0]:
            self.p = 0

        while self.p < (len(self.field) - 1) and time > self.field[self.p + 1][0]:
            self.p += 1

        assert time <= self.field[self.p + 1][0] and time >= self.field[self.p][0]

        pretm = self.field[self.p]
        posttm = self.field[self.p+1]

        if self.flatten_zeroes is not None:
            if (time - pretm[0]) > self.flatten_zeroes:
                pretm = (pretm[0], 0.0)
            if (posttm[0] - time) > self.flatten_zeroes:
                posttm = (posttm[0], 0.0)

        # ok, do the lerp
        totdelt = (posttm[0] - pretm[0]).total_seconds()
        sampdelt = (time - pretm[0]).total_seconds()
        alpha = sampdelt / totdelt
        lerp = pretm[1] * (1.0 - alpha) + posttm[1] * alpha

        return lerp

class FitByTime:
    def __init__(self, name):
        print(f"... loading {name} ...")
        self.fitfile = fitparse.FitFile(name, data_processor = fitparse.StandardUnitsDataProcessor())
        self.fitmessages = list(self.fitfile.get_messages())
        self.fields = {}
        print(f"... massaging data ...")
        for m in self.fitmessages:
            if not isinstance(m, fitparse.DataMessage):
                continue
            if m.name != 'record':
                continue
            vs = m.get_values()
            if 'timestamp' not in vs:
                raise ValueError(f"datamessage {m} does not seem to contain a timestamp?")
            for v in vs:
                if v == 'timestamp':
                    continue
                self.fields[v] = self.fields.get(v, [])
                self.fields[v].append((vs['timestamp'], vs[v], ))

    def interpolator(self, field, flatten_zeroes = None):
        if field not in self.fields:
            print(f"field {field} not in input!")
            return Interpolator(None)
        return Interpolator(self.fields[field], flatten_zeroes = flatten_zeroes)

if __name__ == "__main__":
    f = FitByTime(sys.argv[1])
