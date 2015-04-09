# -*- coding: UTF-8 -*-

import unicodedata
import string
from collections import namedtuple, OrderedDict

import PyICU as icu
from icu import DateFormat, Calendar, DateFormatSymbols

# TODO
#
# - reconhecer a.m. como am (mesmo para p.m.)
# - suportar formatos alternativos para a localidade (por inferência)

DT_YEAR = "year"
DT_MONTH = "month"
DT_WEEKDAY = "wday"
DT_MONTHDAY = "mday"
DT_HOUR = "hour"
DT_MINUTE = "minute"
DT_SECOND = "second"
DT_AMPM = "ampm"

FORMAT_CATEGORY = {
    "yy": DT_YEAR,
    "yyyy": DT_YEAR,
    "y": DT_YEAR,
    "M": DT_MONTH,
    "MM": DT_MONTH,
    "MMM": DT_MONTH,
    "MMMM": DT_MONTH,
    "MMMMM": DT_MONTH,
    "E": DT_WEEKDAY,
    "EE": DT_WEEKDAY,
    "EEE": DT_WEEKDAY,
    "EEEE": DT_WEEKDAY,
    "EEEEE": DT_WEEKDAY,
    "d": DT_MONTHDAY,
    "dd": DT_MONTHDAY,
    "h": DT_HOUR,
    "hh": DT_HOUR,
    "H": DT_HOUR,
    "HH": DT_HOUR,
    "m": DT_MINUTE,
    "mm": DT_MINUTE,
    "s": DT_SECOND,
    "ss": DT_SECOND,
    "a": DT_AMPM,
}

class Token(object):
    tt = None
    tv = None
    pos = None
    ov = None
    tc = None

    def __init__(self, tt, tv, pos, ov, tc=None):
        self.tt = tt
        self.tv = tv
        self.pos = pos
        self.ov = ov
        self.tc = tc

class DateTimeInfo(object):
    _locale = None

    long_months = None
    short_months = None
    long_wdays = None
    short_wdays = None
    ampm_strings = None

    date_format = None
    time_format = None
    datetime_format = None
    timedate_format = None

    def __init__(self, locale_id):
        self._locale = icu.Locale(locale_id)
        self._symbols = DateFormatSymbols(self._locale)

        self.long_months = map(self._normalize, self._symbols.getMonths())
        self.short_months = map(self._normalize, self._symbols.getShortMonths())
        self.long_wdays = self._get_weekdays(DateFormatSymbols.WIDE)
        self.short_wdays = self._get_weekdays(DateFormatSymbols.ABBREVIATED)
        self.ampm_strings = map(self._normalize, self._symbols.getAmPmStrings())

        self.full_date = self._get_date_format(DateFormat.kFull)
        self.long_date = self._get_date_format(DateFormat.kLong)
        self.medium_date = self._get_date_format(DateFormat.kMedium)
        self.short_date = self._get_date_format(DateFormat.kShort)

        self.full_time = self._get_time_format(DateFormat.kFull)
        self.long_time = self._get_time_format(DateFormat.kLong)
        self.medium_time = self._get_time_format(DateFormat.kMedium)
        self.short_time = self._get_time_format(DateFormat.kShort)

    def guess_format(self, s, format_type):
        ipt = self._identify_tokens(self._tokenize(s)).items()
        simple_ipt = filter(lambda x: len(x[1]) > 0, ipt)

        if format_type == "date":
            fmt_list = (
                self.full_date,
                self.long_date,
                self.medium_date,
                self.short_date,
            )

        elif format_type == "time":
            fmt_list = (
                self.full_time,
                self.long_time,
                self.medium_time,
                self.short_time,
            )

        elif format_type == "datetime":
            fmt_list = (
                self.full_date + self.full_time,
                self.long_date + self.full_time,
                self.medium_date + self.full_time,
                self.short_date + self.full_time,

                self.full_date + self.long_time,
                self.long_date + self.long_time,
                self.medium_date + self.long_time,
                self.short_date + self.long_time,

                self.full_date + self.medium_time,
                self.long_date + self.medium_time,
                self.medium_date + self.medium_time,
                self.short_date + self.medium_time,

                self.full_date + self.short_time,
                self.long_date + self.short_time,
                self.medium_date + self.short_time,
                self.short_date + self.short_time,
            )

        elif format_type == "timedate":
            fmt_list = (
                self.full_time + self.full_date,
                self.long_time + self.full_date,
                self.medium_time + self.full_date,
                self.short_time + self.full_date,

                self.full_time + self.long_date,
                self.long_time + self.long_date,
                self.medium_time + self.long_date,
                self.short_time + self.long_date,

                self.full_time + self.medium_date,
                self.long_time + self.medium_date,
                self.medium_time + self.medium_date,
                self.short_time + self.medium_date,

                self.full_time + self.short_date,
                self.long_time + self.short_date,
                self.medium_time + self.short_date,
                self.short_time + self.short_date,
            )

        else:
            raise ValueError("tipo não suportado: %s" % (format_type, ))

        res = []

        for fmt in fmt_list:
            out = self._try_format(simple_ipt, ipt, fmt)

            # _check_format altera tc de cada token, restaura
            for tok, fmtstr_list in ipt:
                tok.tc = None

            if (out is not None) and not (out in res):
                res.append(out)

        return res

    def parse_datetime(self, s, format_type):
        fmt = self.guess_format(s, format_type)

        if not fmt:
            return None

        of = icu.SimpleDateFormat(fmt[0], self._locale)

        return of.parseObject(s)

    def _try_format(self, ipt, original_ipt, fmt):
        itens = self._check_format(ipt, fmt)

        if itens is None:
            return None

        out = ""

        for tok, fmtstr_list in original_ipt:
            if tok.tc:
                fmt_str = None

                for fs in fmtstr_list:
                    fc = self._get_fmt_class(fs)

                    if fc == tok.tc:
                        fmt_str = fs

                        break

                out += fmt_str

                # último fmtstr, ignora restante da string
                if tok is itens[-1]:
                    break

            elif tok.tt == "s":
                out += "'%s'" % (tok.ov, )

            else:
                out += tok.tv

        return out

    def _check_format(self, ipt, fmt):
        i = 0

        while i < len(ipt):
            j = 0

            if self._check_format_class(ipt[i][1], fmt[j].tc):
                start = i

                while (i < len(ipt)) \
                        and (j < len(fmt)) \
                        and self._check_format_class(ipt[i][1], fmt[j].tc):
                    ipt[i][0].tc = fmt[j].tc
                    i += 1
                    j += 1

                if j == len(fmt):
                    return map(lambda x: x[0], ipt[start:start + j])

                else:
                    i = start + 1

            else:
                i += 1

        return None

    def _check_format_class(self, fmt_list, fmt_class):
        for fmt in fmt_list:
            fc = self._get_fmt_class(fmt)

            if fc and (fc == fmt_class):
                return True

        return False

    def _classify_tokens(self, tokens):
        for t in tokens:
            if (t.tt == "f") and FORMAT_CATEGORY.has_key(t.tv):
                t.tc = FORMAT_CATEGORY[t.tv]

    def _get_fmt_class(self, fmt_str):
        return FORMAT_CATEGORY[fmt_str] \
                if FORMAT_CATEGORY.has_key(fmt_str) \
                else None

    def _normalize(self, s):
        return self._strip_acents(s).lower()

    def _strip_acents(self, s):
        temp = unicodedata.normalize("NFD", s)
        s = "".join((c for c in temp if unicodedata.category(c) != "Mn"))

        return s

    def _tokenize(self, s):
        pos = 0
        it = iter(self._strip_acents(s).lower())

        def nextch():
            try:
                return next(it)

            except StopIteration:
                return None

        c = nextch()
        buf = ""

        while c:
            if c in string.ascii_letters + "-":
                start = pos
                buf += c
                c = nextch()
                pos += 1

                while c and (c in string.ascii_letters + "-"):
                    buf += c
                    pos += 1
                    c = nextch()

                yield Token("s", buf, start, s[start:pos])

                buf = ""

            elif c in string.digits:
                start = pos
                buf += c
                c = nextch()
                pos += 1

                while c and (c in string.digits):
                    buf += c
                    pos += 1
                    c = nextch()

                yield Token("i", buf, start, s[start:pos])

                buf = ""

            elif c.isspace():
                start = pos
                buf += c
                c = nextch()
                pos += 1

                while c and c.isspace():
                    buf += c
                    pos += 1
                    c = nextch()

                yield Token("w", buf, start, s[start:pos])

                buf = ""

            else:
                yield Token(c, c, pos, s[pos])

                c = nextch()
                pos += 1

    def _tokenize_icu_pattern(self, s):
        pos = 0
        it = iter(s)

        def nextch():
            try:
                return next(it)

            except StopIteration:
                return None

        c = nextch()

        while c:
            if c in string.ascii_letters:
                start = pos
                buf = c
                c = nextch()
                pos += 1

                while c and (c in string.ascii_letters):
                    buf += c
                    c = nextch()
                    pos += 1

                yield Token("f", buf, start, s[start:pos])

            elif c == "'":
                start = pos
                buf = ""
                c = nextch()
                pos += 1

                while c and (c != "'"):
                    buf += c
                    pos += 1
                    c = nextch()

                yield Token("l", buf, start, s[start:pos])

                c = nextch()
                pos += 1

            elif c.isspace():
                start = pos
                buf = c
                c = nextch()
                pos += 1

                while c and c.isspace():
                    buf += c
                    pos += 1
                    c = nextch()

                yield Token("w", buf, start, s[start:pos])

            else:
                yield Token(c, c, pos, s[pos])

                c = nextch()
                pos += 1

    def _identify_tokens(self, tl):
        res = OrderedDict()

        for t in tl:
            c = []

            if t.tt == "i":
                iv = int(t.tv)

                if iv <= 12:
                    c.extend(["M", "MM"])

                    if iv > 0:
                        c.extend(["h", "hh"])

                if iv <= 24:
                    if iv < 24:
                        c.extend(["H", "HH"])

                if iv <= 31:
                    c.extend(["d", "dd"])

                if iv <= 59:
                    c.extend(["m", "mm"])
                    c.extend(["s", "ss"])

                if len(t.tv) > 2:
                    c.extend(["y", "yyyy"])

                else:
                    c.append("yy")

            elif t.tt == "s":
                temp = self._normalize(t.tv)

                if temp in self.long_months:
                    c.append("MMMM")

                elif temp in self.short_months:
                    c.append("MMM")

                if temp in self.long_wdays:
                    c.append("EEEE")

                elif temp in self.short_wdays:
                    c.append("EEE")

                if temp in self.ampm_strings:
                    c.append("a")

            res[t] = c

        return res

    def _get_weekdays(self, width):
        if width == DateFormatSymbols.WIDE:
            temp = self._symbols.getWeekdays()

        else: # width == DateFormatSymbols.ABBREVIATED
            temp = self._symbols.getShortWeekdays()

        wdays = (
            temp[Calendar.SUNDAY],
            temp[Calendar.MONDAY],
            temp[Calendar.TUESDAY],
            temp[Calendar.WEDNESDAY],
            temp[Calendar.THURSDAY],
            temp[Calendar.FRIDAY],
            temp[Calendar.SATURDAY],
        )

        return map(self._normalize, wdays)

    def _get_date_format(self, fmt_type):
        df = DateFormat.createDateInstance(fmt_type, self._locale)
        temp = self._tokenize_icu_pattern(df.toPattern())
        fmt = filter(lambda x: x.tt == "f", temp)
        self._classify_tokens(fmt)

        return fmt

    def _get_time_format(self, fmt_type):
        df = DateFormat.createTimeInstance(fmt_type, self._locale)
        temp = self._tokenize_icu_pattern(df.toPattern())
        fmt = filter(lambda x: x.tt == "f", temp)
        self._classify_tokens(fmt)

        return fmt
