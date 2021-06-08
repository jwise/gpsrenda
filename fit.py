import fitparse
import datetime
import sys

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
    
    # XXX: this gets n^2 in a hurry
    def lerp_value(self, time, field, flatten_zeroes = None):
        if field not in self.fields:
            return None
        # if there is a field, its length >= 1
        
        # time requested is out of range early?
        if time < self.fields[field][0][0]:
            return None
        pretm = self.fields[field][0]
        posttm = self.fields[field][0]
        for samp in self.fields[field]:
            pretm = posttm
            posttm = samp
            # got it exactly?
            if samp[0] == time:
                return samp[1]
            if samp[0] > time:
                break
        
        # time requested is out of range late?
        if posttm[0] < time:
            return None
        
        if flatten_zeroes is not None:
            if (time - pretm[0]) > flatten_zeroes:
                pretm = (pretm[0], 0.0)
            if (posttm[0] - time) > flatten_zeroes:
                posttm = (posttm[0], 0.0)
        
        # ok, do the lerp
        totdelt = (posttm[0] - pretm[0]).total_seconds()
        sampdelt = (time - pretm[0]).total_seconds()
        alpha = sampdelt / totdelt
        lerp = pretm[1] * (1.0 - alpha) + posttm[1] * alpha
        
        # print(f"lerping {field} between {pretm[0]} -> {pretm[1]} and {posttm[0]} -> {posttm[1]} with alpha {alpha} = {time} -> {lerp}")
                
        return lerp
        
if __name__ == "__main__":
    f = FitByTime(sys.argv[1])
