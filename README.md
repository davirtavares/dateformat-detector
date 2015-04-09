# dateformat-detector

Little Python lib for detecting the date/time format of a given string.

This lib should be useful for guessing date and time string of webpages, should not be confused with datetime guessing and extraction. This lib only detects the format (the same used to convert to human-readable), this difference brings great performance improvements and reliably, as parsing datetime with a known format is far alway fast from trying to detect it. Once parsed one could store it and raise an error if an expected page changes its date/time format.

For locale info, it's used PyICU (libICU wrapper). So it tries to distinguish date part positions as well long month names, weekdays and so, independently of locale.
