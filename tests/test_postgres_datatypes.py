import os
import datetime
import copy
import unittest
import decimal
import uuid
import json

from psycopg2.extensions import quote_ident
import psycopg2.extras
import pytz
from tap_tester.scenario import (SCENARIOS)
import tap_tester.connections as connections
import tap_tester.menagerie   as menagerie
import tap_tester.runner      as runner

import db_utils  # pylint: disable=import-error
import datatype_file_reader as dfr  # pylint: disable=import-error

test_schema_name = "public"
test_table_name = "postgres_datatypes_test"
test_db = "dev"

expected_schema = {'OUR DATE': {'format': 'date-time', 'type': ['null', 'string']},
                   'OUR TIME': {'type': ['null', 'string']},
                   'OUR TIME TZ': {'type': ['null', 'string']},
                   'OUR TS': {'format': 'date-time', 'type': ['null', 'string']},
                   'OUR TS TZ': {'format': 'date-time', 'type': ['null', 'string']},
                   'id': {'maximum': 2147483647, 'minimum': -2147483648, 'type': ['integer']},
                   'unsupported_bit': {},
                   'unsupported_bit_varying': {},
                   'unsupported_box': {},
                   'unsupported_bytea': {},
                   'unsupported_circle': {},
                   'unsupported_interval': {},
                   'unsupported_line': {},
                   'unsupported_lseg': {},
                   'unsupported_path': {},
                   'unsupported_pg_lsn': {},
                   'unsupported_point': {},
                   'unsupported_polygon': {},
                   'unsupported_tsquery': {},
                   'unsupported_tsvector': {},
                   'unsupported_txid_snapshot': {},
                   'unsupported_xml': {},
                   'our_alignment_enum': {'type': ['null', 'string']},
                   'our_bigint': {'maximum': 9223372036854775807,
                                  'minimum': -9223372036854775808,
                                  'type': ['null', 'integer']},
                   'our_bigserial': {'maximum': 9223372036854775807,
                                     'minimum': -9223372036854775808,
                                     'type': ['null', 'integer']},
                   'our_bit': {'type': ['null', 'boolean']},
                   'our_boolean': {'type': ['null', 'boolean']},
                   'our_char': {'maxLength': 1, 'type': ['null', 'string']},
                   'our_char_big': {'maxLength': 10485760, 'type': ['null', 'string']},
                   'our_cidr': {'type': ['null', 'string']},
                   'our_citext': {'type': ['null', 'string']},
                   'our_decimal': {'exclusiveMaximum': True,
                                   'exclusiveMinimum': True,
                                   'maximum': 100000000000000000000000000000000000000000000000000000000000000,
                                   'minimum': -100000000000000000000000000000000000000000000000000000000000000,
                                   'multipleOf': "Decimal('1E-38')",
                                   'type': ['null', 'number']},
                   'our_double': {'type': ['null', 'number']},
                   'our_inet': {'type': ['null', 'string']},
                   'our_integer': {'maximum': 2147483647,
                                   'minimum': -2147483648,
                                   'type': ['null', 'integer']},
                   'our_json': {'type': ['null', 'string']}, # TODO Should this have a format??
                   'our_jsonb': {'type': ['null', 'string']},
                   'our_mac': {'type': ['null', 'string']},
                   'our_money': {'type': ['null', 'string']},
                   'our_nospec_decimal': {'exclusiveMaximum': True,
                                          'exclusiveMinimum': True,
                                          'maximum': 100000000000000000000000000000000000000000000000000000000000000,
                                          'minimum': -100000000000000000000000000000000000000000000000000000000000000,
                                          'multipleOf': "Decimal('1E-38')",
                                          'type': ['null', 'number']},
                   'our_nospec_numeric': {'exclusiveMaximum': True,
                                          'exclusiveMinimum': True,
                                          'maximum': 100000000000000000000000000000000000000000000000000000000000000,
                                          'minimum': -100000000000000000000000000000000000000000000000000000000000000,
                                          'multipleOf': "Decimal('1E-38')",
                                          'type': ['null', 'number']},
                   'our_numeric': {'exclusiveMaximum': True,
                                   'exclusiveMinimum': True,
                                   'maximum': 100000000000000000000000000000000000000000000000000000000000000,
                                   'minimum': -100000000000000000000000000000000000000000000000000000000000000,
                                   'multipleOf': "Decimal('1E-38')",
                                   'type': ['null', 'number']},
                   'our_real': {'type': ['null', 'number']},
                   'our_serial': {'maximum': 2147483647,
                                  'minimum': -2147483648,
                                  'type': ['null', 'integer']},
                   'our_smallint': {'maximum': 32767,
                                    'minimum': -32768,
                                    'type': ['null', 'integer']},
                   'our_smallserial': {'maximum': 32767,
                                       'minimum': -32768,
                                       'type': ['null', 'integer']},
                   'our_hstore': {'properties': {}, 'type': ['null', 'object']},
                   'our_text': {'type': ['null', 'string']},
                   'our_text_2': {'type': ['null', 'string']},
                   'our_uuid': {'type': ['null', 'string']},
                   'our_varchar': {'type': ['null', 'string']},
                   'our_varchar_big': {'maxLength': 10485760, 'type': ['null', 'string']}}


decimal.getcontext().prec = 131072 + 16383

whitespace = ' \t\n\r\v\f'
ascii_lowercase = 'abcdefghijklmnopqrstuvwxyz'
ascii_uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
ascii_letters = ascii_lowercase + ascii_uppercase
digits = '0123456789'
punctuation = r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""
our_ascii = ascii_letters + digits + punctuation + whitespace

class PostgresDatatypes(unittest.TestCase):
    """
    TODO | My Running list


    Arbitrary Precision Numbers
    Numeric | exact	up to 131072 digits before the decimal point; up to 16383 digits after the decimal point
              when precision is explicitly stated, maximum is 1000 digits
    TODOs
      - Generate 3 different fields with NUMERIC,  NUMERIC(precision, scale),  NUMERIC(precision).
      - Cover Maximum precision and scale
      - Cover Minimum precision and scale
      - Cover NaN


    Floating-Point Types
      - usually implementations of IEEE Standard 754 for Binary Floating-Point Arithmetic
      - on most platforms, the real type has a range of at least 1E-37 to 1E+37 with a precision of at least 6 decimal digits
      - double precision type typically has a range of around 1E-307 to 1E+308 with a precision of at least 15 digits
      - numbers too close to zero that are not representable as distinct from zero will cause an underflow error.
    TODOs
      - Cover NaN, -Inf, Inf
      -


    Character
      -
    TODOS
      - Generate different fields with VARCHAR,  VARCHAR(n),  CHAR,  CHAR(n)
      - VARCHAR(10485760)
      - Generate a 1 GB string??
      - Cover the following character sets:
             LATIN1	ISO 8859-1, ECMA 94	Western European	Yes	1	ISO88591
             LATIN2	ISO 8859-2, ECMA 94	Central European	Yes	1	ISO88592
             LATIN3	ISO 8859-3, ECMA 94	South European	Yes	1	ISO88593
             LATIN4	ISO 8859-4, ECMA 94	North European	Yes	1	ISO88594
             LATIN5	ISO 8859-9, ECMA 128	Turkish	Yes	1	ISO88599
             LATIN6	ISO 8859-10, ECMA 144	Nordic	Yes	1	ISO885910
             LATIN7	ISO 8859-13	Baltic	Yes	1	ISO885913
             LATIN8	ISO 8859-14	Celtic	Yes	1	ISO885914
             LATIN9	ISO 8859-15	LATIN1 with Euro and accents	Yes	1	ISO885915
             LATIN10	ISO 8859-16, ASRO SR 14111	Romanian	Yes	1	ISO885916
             UTF8	Unicode, 8-bit	all	Yes	1-4	Unicode


    Binary Types
    Bytea | binary string, sequence of octets can be written in hex or escape
    TODOs
      - Generate different fields for hex and escape


    Network Address Types
    TODOs
      - Do with and without 'y' where input is number of bits in the netmask: input looks like 'address/y'
      - For inet/cidr 'y' will default ot 32 for ipv4 and 128 for ipv6
      - For mac do all the input formats
         [] '08:00:2b:01:02:03'
         [] '08-00-2b-01-02-03'
         [] '08002b:010203'
         [] '08002b-010203'
         [] '0800.2b01.0203'
         [] '08002b010203'


    Datestimes
    TODOs
      - Test values with second, millisecond and micrsecond precision
      - Test all precisions 0..6

    UUID
    TODOs
      - uuid.uuid1(node=None, clock_seq=None)
      Generate a UUID from a host ID, sequence number, and the current time. If node is not given, getnode() is used to obtain the hardware address. If clock_seq is given, it is used as the sequence number; otherwise a random 14-bit sequence number is chosen.

      - uuid.uuid3(namespace, name)
      Generate a UUID based on the MD5 hash of a namespace identifier (which is a UUID) and a name (which is a string).

      - uuid.uuid4()
      Generate a random UUID.

      - uuid.uuid5(namespace, name)
      Generate a UUID based on the SHA-1 hash of a namespace identifier (which is a UUID) and a name (which is a string).

    """

    AUTOMATIC_FIELDS = "automatic"
    REPLICATION_KEYS = "valid-replication-keys"
    PRIMARY_KEYS = "table-key-properties"
    FOREIGN_KEYS = "table-foreign-key-properties"
    REPLICATION_METHOD = "forced-replication-method"
    API_LIMIT = "max-row-limit"
    INCREMENTAL = "INCREMENTAL"
    FULL_TABLE = "FULL_TABLE"
    LOG_BASED = "LOG_BASED"

    UNSUPPORTED_TYPES = {
        "BIGSERIAL",
        "BIT VARYING",
        "BOX",
        "BYTEA",
        "CIRCLE",
        "INTERVAL",
        "LINE",
        "LSEG",
        "PATH",
        "PG_LSN",
        "POINT",
        "POLYGON",
        "SERIAL",
        "SMALLSERIAL",
        "TSQUERY",
        "TSVECTOR",
        "TXID_SNAPSHOT",
        "XML",
    }
    default_replication_method = ""

    def tearDown(self):
        pass
        # with db_utils.get_test_connection(test_db) as conn:
        #     conn.autocommit = True
        #     with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        #         cur.execute(""" SELECT pg_drop_replication_slot('stitch') """)

    def setUp(self):
        db_utils.ensure_environment_variables_set()

        db_utils.ensure_db(test_db)
        self.maxDiff = None

        with db_utils.get_test_connection(test_db) as conn:
            conn.autocommit = True
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:

                # db_utils.ensure_replication_slot(cur, test_db)

                canonicalized_table_name = db_utils.canonicalized_table_name(cur, test_schema_name, test_table_name)

                db_utils.set_db_time_zone(cur, '+15:59')  #'America/New_York')

                create_table_sql = """
CREATE TABLE {} (id                       SERIAL PRIMARY KEY,
                our_varchar               VARCHAR,
                our_varchar_big           VARCHAR(10485760),
                our_char                  CHAR,
                our_char_big              CHAR(10485760),
                our_text                  TEXT,
                our_text_2                TEXT,
                our_integer               INTEGER,
                our_smallint              SMALLINT,
                our_bigint                BIGINT,
                our_nospec_numeric        NUMERIC,
                our_numeric               NUMERIC(1000, 500),
                our_nospec_decimal        DECIMAL,
                our_decimal               DECIMAL(1000, 500),
                "OUR TS"                  TIMESTAMP WITHOUT TIME ZONE,
                "OUR TS TZ"               TIMESTAMP WITH TIME ZONE,
                "OUR TIME"                TIME WITHOUT TIME ZONE,
                "OUR TIME TZ"             TIME WITH TIME ZONE,
                "OUR DATE"                DATE,
                our_double                DOUBLE PRECISION,
                our_real                  REAL,
                our_boolean               BOOLEAN,
                our_bit                   BIT(1),
                our_json                  JSON,
                our_jsonb                 JSONB,
                our_uuid                  UUID,
                our_hstore                HSTORE,
                our_citext                CITEXT,
                our_cidr                  cidr,
                our_inet                  inet,
                our_mac                   macaddr,
                our_alignment_enum        ALIGNMENT,
                our_money                 money,
                our_bigserial             BIGSERIAL,
                unsupported_bit           BIT(80),
                unsupported_bit_varying   BIT VARYING(80),
                unsupported_box           BOX,
                unsupported_bytea         BYTEA,
                unsupported_circle        CIRCLE,
                unsupported_interval      INTERVAL,
                unsupported_line          LINE,
                unsupported_lseg          LSEG,
                unsupported_path          PATH,
                unsupported_pg_lsn        PG_LSN,
                unsupported_point         POINT,
                unsupported_polygon       POLYGON,
                our_serial                SERIAL,
                our_smallserial           SMALLSERIAL,
                unsupported_tsquery       TSQUERY,
                unsupported_tsvector      TSVECTOR,
                unsupported_txid_snapshot TXID_SNAPSHOT,
                unsupported_xml           XML)
                """.format(canonicalized_table_name)

                cur = db_utils.ensure_fresh_table(conn, cur, test_schema_name, test_table_name)
                cur.execute(create_table_sql)


                # insert fixture data and track expected records by test cases
                self.inserted_records = []
                self.expected_records = dict()

                
                # insert a record wtih minimum values
                our_tz = pytz.timezone('Singapore')  # GMT+8
                min_date = datetime.date(1, 1, 1)
                my_absurdly_small_decimal = decimal.Decimal('-' + '9' * 38 + '.' + '9' * 38) # THIS IS OUR LIMIT IN THE TARGET}
                # TODO |  BUG ? | The target blows up with greater than 38 digits before/after the decimal.
                #                 Is this a known/expected behavior or a BUG in the target?
                #                 It prevents us from testing what the tap claims to be able to support (100 precision, 38 scale) without rounding AND..
                #                 The postgres limits WITH rounding.
                # my_absurdly_small_decimal = decimal.Decimal('-' + '9' * 38 + '.' + '9' * 38) # THIS IS OUR LIMIT IN THE TARGET
                # my_absurdly_small_decimal = decimal.Decimal('-' + '9' * 62 + '.' + '9' * 37) # 131072 + 16383
                # my_absurdly_small_spec_decimal = decimal.Decimal('-' + '9'*500 + '.' + '9'*500)
                self.inserted_records.append({
                    'id': 1,# SERIAL PRIMARY KEY,
                    'our_char': "a",  #    CHAR,
                    'our_varchar': "",  #    VARCHAR,
                    'our_varchar_big': "",  #   VARCHAR(10485760),
                    'our_char_big': "a",  #   CHAR(10485760),
                    'our_text': "",  #   TEXT
                    'our_text_2': "",  #   TEXT, TODO move our_ascii into it's own record
                    'our_integer': -2147483648,  #    INTEGER,
                    'our_smallint': -32768,  #   SMALLINT,
                    'our_bigint': -9223372036854775808,  #       BIGINT,
                    'our_nospec_numeric': my_absurdly_small_decimal,  #    NUMERIC,
                    'our_numeric': my_absurdly_small_decimal,  #           NUMERIC(1000, 500),
                    'our_nospec_decimal': my_absurdly_small_decimal,  #    DECIMAL,
                    'our_decimal': my_absurdly_small_decimal,  #           DECIMAL(1000, 500),
                    quote_ident('OUR TS', cur): '0001-01-01T00:00:00.000001', # '4713-01-01 00:00:00.000000 BC',  #    TIMESTAMP WITHOUT TIME ZONE,
                    quote_ident('OUR TS TZ', cur): '0001-01-01T00:00:00.000001-15:59',#_tz, #'4713-01-01 00:00:00.000000 BC',  #    TIMESTAMP WITH TIME ZONE,
                    quote_ident('OUR TIME', cur): '00:00:00.000001',  #   TIME WITHOUT TIME ZONE,
                    quote_ident('OUR TIME TZ', cur): '00:00:00.000001-15:59',  #    TIME WITH TIME ZONE,
                    quote_ident('OUR DATE', cur): min_date,# '4713-01-01 BC',  #   DATE,
                    'our_double': -1.79769313486231e+308, # DOUBLE PRECISION
                    'our_real': decimal.Decimal('-3.40282e+38'), #   REAL,
                    'our_boolean': False,  #    BOOLEAN,
                    'our_bit': '0',  #    BIT(1),
                    'our_json': json.dumps(dict()),  #       JSON,
                    'our_jsonb': json.dumps(dict()),  #    JSONB,
                    'our_uuid': '00000000-0000-0000-0000-000000000000', # str(uuid.uuid1())
                    'our_hstore': None,  # HSTORE,
                    'our_citext': "",  # CITEXT,
                    'our_cidr': '12.244.233.165/32',  # cidr,
                    'our_inet': '12.244.233.165/32',  # inet,
                    'our_mac': '08:00:2b:01:02:04',#'12.244.233.165/32',  # macaddr,
                    'our_alignment_enum': None,  # ALIGNMENT,
                    'our_money': '-$92,233,720,368,547,758.08',  # money, TODO THis throws pyscopg error
                    'our_bigserial': 1,  # BIGSERIAL,
                    'our_serial': 1,  # SERIAL,
                    'our_smallserial': 1,  #  SMALLSERIAL,
                })
                self.expected_records['minimum_boundary_general'] = copy.deepcopy(self.inserted_records[-1])
                self.expected_records['minimum_boundary_general'].update({
                    'our_char_big': "a" + (10485760 - 1) * " ", # padded
                    'our_double':  decimal.Decimal('-1.79769313486231e+308'),
                    'OUR TS': '0001-01-01T00:00:00.000001+00:00',
                    'OUR TS TZ': '0001-01-01T15:59:00.000001+00:00',
                    'OUR TIME': '00:00:00.000001',
                    'OUR TIME TZ': '00:00:00.000001-15:59',
                    'OUR DATE': '0001-01-01T00:00:00+00:00',
                    'our_bit': False,
                    'our_jsonb': json.loads(self.inserted_records[-1]['our_jsonb']),
                    'our_inet': '12.244.233.165',
                })
                my_keys = set(self.expected_records['minimum_boundary_general'].keys())
                for key in my_keys:
                    if key.startswith('"'):
                        del self.expected_records['minimum_boundary_general'][key]

                db_utils.insert_record(cur, test_table_name, self.inserted_records[-1])


                # insert a record wtih maximum values
                max_ts = datetime.datetime(9999, 12, 31, 23, 59, 59, 999999)
                # our_ts = datetime.datetime(1997, 2, 2, 2, 2, 2, 722184)
                # nyc_tz = pytz.timezone('America/New_York')
                # our_ts_tz = nyc_tz.localize(our_ts)
                # our_time  = datetime.time(12,11,10)
                # our_time_tz = our_time.isoformat() + "-04:00"
                max_date = datetime.date(9999, 12, 31)
                base_string = "Bread Sticks From Olive Garden"
                my_absurdly_large_decimal = decimal.Decimal('9' * 38 + '.' + '9' * 38) # THIS IS OUR LIMIT IN THE TARGET}
                # 🥖 = 1f956
                self.inserted_records.append({
                    'id': 2147483647,  # SERIAL PRIMARY KEY,
                    'our_char': "🥖",  #    CHAR,
                    'our_varchar': "a", #* 20971520,  #    VARCHAR,
                    'our_varchar_big': "🥖" + base_string,  #   VARCHAR(10485714),
                    'our_char_big': "🥖",  #   CHAR(10485760),
                    'our_text': "apples", #dfr.read_in("text"),  #   TEXT,
                    'our_text_2': None,  #   TEXT,
                    'our_integer': 2147483647,  #    INTEGER,
                    'our_smallint': 32767,  #   SMALLINT,
                    'our_bigint': 9223372036854775807,  #       BIGINT,
                    'our_nospec_numeric': my_absurdly_large_decimal,  #    NUMERIC,
                    'our_numeric': my_absurdly_large_decimal,  #           NUMERIC(1000, 500),
                    'our_nospec_decimal': my_absurdly_large_decimal,  #    DECIMAL,
                    'our_decimal': my_absurdly_large_decimal,  #           NUMERIC(1000, 500),
                    quote_ident('OUR TS', cur): max_ts,# '9999-12-31 24:00:00.000000',# '294276-12-31 24:00:00.000000',  #   TIMESTAMP WITHOUT TIME ZONE,
                    quote_ident('OUR TS TZ', cur): '9999-12-31T08:00:59.999999-15:59', #max_ts, #'294276-12-31 24:00:00.000000',  #    TIMESTAMP WITH TIME ZONE,
                    quote_ident('OUR TIME', cur): '23:59:59.999999',# '24:00:00.000000' ->,  #   TIME WITHOUT TIME ZONE,
                    # '24:00:00.000000'  -> 00:00:00 TODO BUG?
                    quote_ident('OUR TIME TZ', cur): '23:59:59.999999+1559',  #    TIME WITH TIME ZONE,
                    quote_ident('OUR DATE', cur): '5874897-12-31',  #   DATE,
                    'our_double': decimal.Decimal('9.99999999999999'), # '1E308',  # DOUBLE PRECISION,
                    'our_real':  decimal.Decimal('9.99999'), # '1E308',  #   REAL, # TODO
                    'our_boolean': True,  #    BOOLEAN
                    'our_bit': '1',  #    BIT(1),
                    'our_json': json.dumps({
                        'our_json_string': 'This is our JSON string type.',
                        'our_json_number': 666,
                        'our_json_object': {
                            'our_json_string': 'This is our JSON string type.',
                            'our_json_number': 666,
                            'our_json_object': {'calm': 'down'},
                            'our_json_array': ['our_json_arrary_string', 6, {'calm': 'down'}, False, None],
                            'our_json_boolean': True,
                            'our_json_null': None,
                        },
                        'our_json_array': ['our_json_arrary_string', 6, {'calm': 'down'}, False, None],
                        'our_json_boolean': True,
                        'our_json_null': None,
                    }),  #       JSON,
                    'our_jsonb': json.dumps({
                        'our_jsonb_string': 'This is our JSONB string type.',
                        'our_jsonb_number': 666,
                        'our_jsonb_object': {
                            'our_jsonb_string': 'This is our JSONB string type.',
                            'our_jsonb_number': 666,
                            'our_jsonb_object': {'calm': 'down'},
                            'our_jsonb_array': ['our_jsonb_arrary_string', 6, {'calm': 'down'}, False, None],
                            'our_jsonb_boolean': True,
                            'our_jsonb_null': None,
                        },
                        'our_jsonb_array': ['our_jsonb_arrary_string', 6, {'calm': 'down'}, False, None],
                        'our_jsonb_boolean': True,
                        'our_jsonb_null': None,
                    }),  #    JSONB,
                    'our_uuid':'ffffffff-ffff-ffff-ffff-ffffffffffff', # UUID,
                    'our_hstore': '"foo"=>"bar","bar"=>"foo","dumdum"=>Null',  # HSTORE,
                    'our_citext': "aPpLeS",  # CITEXT,
                    'our_cidr': '2001:0db8:0000:0000:0000:ff00:0042:7879/128',  # cidr,
                    'our_inet': '12.244.233.165/24',# TODO IPV6 value is rejected by pyscopg '2001:0db8:2222:3333:ghdk:ff00:0042:7879/128',  # inet,
                    'our_mac': '08:00:2b:01:02:03',  # macaddr
                    'our_alignment_enum': 'u g l y',  # ALIGNMENT,
                    'our_money': "$92,233,720,368,547,758.07",  # money,
                    'our_bigserial': 9223372036854775807,  # BIGSERIAL,
                    'our_serial': 2147483647,  # SERIAL,
                    'our_smallserial': 32767, #2147483647,  #  SMALLSERIAL,
                })

                self.expected_records['maximum_boundary_general'] = copy.deepcopy(self.inserted_records[-1])
                self.expected_records['maximum_boundary_general'].update({
                    'OUR TS': '9999-12-31T23:59:59.999999+00:00',
                    'OUR TS TZ': '9999-12-31T23:59:59.999999+00:00',
                    'OUR TIME': '23:59:59.999999',
                    'OUR TIME TZ': '23:59:59.999999+15:59',
                    'OUR DATE': '9999-12-31T00:00:00+00:00',
                    'our_char_big': "🥖" + " " * 10485759,
                    'our_bit': True,
                    'our_cidr': '2001:db8::ff00:42:7879/128',
                    'our_jsonb': json.loads(self.inserted_records[-1]['our_jsonb']),
                    'our_hstore': {'foo': 'bar', 'bar': 'foo', 'dumdum': None},
                })
                my_keys = set(self.expected_records['maximum_boundary_general'].keys())
                for key in my_keys:
                    if key.startswith('"'):
                        del self.expected_records['maximum_boundary_general'][key]

                db_utils.insert_record(cur, test_table_name, self.inserted_records[-1])


                # insert a record with valid values for unsupported types
                self.inserted_records.append({
                    'id': 9999,
                    'unsupported_bit_varying': '01110100011000010111000000101101011101000110010101110011011101000110010101110010',  # BIT VARYING(80),
                    'unsupported_bit': '01110100011000010111000000101101011101000110010101110011011101000110010101110010',  #    BIT(80),
                    'unsupported_box': '((50, 50), (0, 0))',  # BOX,
                    'unsupported_bytea': "E'\\255'",  # BYTEA,
                    'unsupported_circle': '< (3, 1), 4 >',  # CIRCLE,
                    'unsupported_interval': '178000000 years',  # INTERVAL,
                    'unsupported_line': '{6, 6, 6}',  # LINE,
                    'unsupported_lseg': '(0 , 45), (45, 90)',  # LSEG,
                    'unsupported_path': '((0, 0), (45, 90), (2, 56))',  # PATH,
                    'unsupported_pg_lsn': '16/B374D848',  # PG_LSN,
                    'unsupported_point': '(1, 2)',  # POINT,
                    'unsupported_polygon': '((0, 0), (0, 10), (10, 0), (4, 5), (6, 7))',  #  POLYGON,
                    'unsupported_tsquery': "'fat' & 'rat'",  #  TSQUERY,
                    'unsupported_tsvector':  "'fat':2 'rat':3",  # TSVECTOR,
                    'unsupported_txid_snapshot': '10:20:10,14,15',  # TXID_SNAPSHOT,
                    'unsupported_xml': '<foo>bar</foo>',  # XML)
                })
                self.expected_records['unsupported_types'] = {
                    'id': 9999,
                }

                db_utils.insert_record(cur, test_table_name, self.inserted_records[-1])


                # add a record with a text value ~ 10 Megabytes
                self.inserted_records.append({
                    'id': 666,
                    'our_text': dfr.read_in('text')
                })
                self.expected_records['maximum_boundary_text'] = {
                    'id': self.inserted_records[-1]['id'],
                    'our_text': self.inserted_records[-1]['our_text'],
                }

                db_utils.insert_record(cur, test_table_name, self.inserted_records[-1])

                #                 # 🥖 = 1f956
                # self.inserted_records.append({
                #     'id': 2147483647,  # SERIAL PRIMARY KEY,
                #     'our_char': "🥖",  #    CHAR,
                #     'our_varchar': "a" * 20971520  #    VARCHAR,
                #     'our_varchar_big': "🥖" * 5242880base_string,  #   VARCHAR(10485760),
                #     'our_char_big': "🥖",  #   CHAR(10485760),

                # add a record with a text value ~ 10 Megabytes


    @staticmethod
    def expected_check_streams():
        return { 'postgres_datatypes_test'}

    @staticmethod
    def expected_sync_streams():
        return { 'postgres_datatypes_test'}

    def expected_check_stream_ids(self):
        """A set of expected table names in <collection_name> format"""
        check_streams = self.expected_check_streams()
        return {"{}-{}-{}".format(test_db, test_schema_name, stream) for stream in check_streams}

    @staticmethod
    def expected_primary_keys():
        return {
            'postgres_datatypes_test' : {'id'}
        }

    @staticmethod
    def expected_unsupported_fields():
        return {
            'unsupported_bigserial',
            'unsupported_bit_varying',
            'unsupported_box',
            'unsupported_bytea',
            'unsupported_circle',
            'unsupported_interval',
            'unsupported_line',
            'unsupported_lseg',
            'unsupported_path',
            'unsupported_pg_lsn',
            'unsupported_point',
            'unsupported_polygon',
            'unsupported_serial',
            'unsupported_smallserial',
            'unsupported_tsquery',
            'unsupported_tsvector',
            'unsupported_txid_snapshot',
            'unsupported_xml',
        }

    @staticmethod
    def expected_schema_types():
        return {
            'id': 'integer',  # 'serial primary key',
            'our_varchar': 'character varying',  # 'varchar'
            'our_varchar_10': 'character varying',  # 'varchar(10)',
            'our_text': 'text',
            'our_text_2': 'text',
            'our_integer': 'integer',
            'our_smallint': 'smallint',
            'our_bigint': 'bigint',
            'our_decimal': 'numeric',
            'OUR TS': 'timestamp without time zone',
            'OUR TS TZ': 'timestamp with time zone',
            'OUR TIME': 'time without time zone',
            'OUR TIME TZ': 'time with time zone',
            'OUR DATE': 'date',
            'our_double': 'double precision',
            'our_real': 'real',
            'our_boolean': 'boolean',
            'our_bit': 'bit',
            'our_json': 'json',
            'our_jsonb': 'jsonb',
            'our_uuid': 'uuid',
            'our_hstore': 'hstore',
            'our_citext': 'citext',
            'our_cidr': 'cidr',
            'our_inet': 'inet',
            'our_mac': 'macaddr',
            'our_alignment_enum': 'alignment',
            'our_money': 'money',
            'unsupported_bigserial': 'bigint',
            'unsupported_bit_varying': 'bit varying',
            'unsupported_box': 'box',
            'unsupported_bytea': 'bytea',
            'unsupported_circle': 'circle',
            'unsupported_interval': 'interval',
            'unsupported_line': 'line',
            'unsupported_lseg': 'lseg',
            'unsupported_path': 'path',
            'unsupported_pg_lsn': 'pg_lsn',
            'unsupported_point': 'point',
            'unsupported_polygon': 'polygon',
            'unsupported_serial': 'integer',
            'unsupported_smallserial': 'smallint',
            'unsupported_tsquery': 'tsquery',
            'unsupported_tsvector': 'tsvector',
            'unsupported_txid_snapshot': 'txid_snapshot',
            'unsupported_xml': 'xml',
        }

    @staticmethod
    def tap_name():
        return "tap-postgres"

    @staticmethod
    def name():
        return "tap_tester_postgres_datatypes"

    @staticmethod
    def get_type():
        return "platform.postgres"

    @staticmethod
    def get_credentials():
        return {'password': os.getenv('TAP_POSTGRES_PASSWORD')}

    def get_properties(self, original_properties=True):
        return_value = {
            'host' : os.getenv('TAP_POSTGRES_HOST'),
            'dbname' : os.getenv('TAP_POSTGRES_DBNAME'),
            'port' : os.getenv('TAP_POSTGRES_PORT'),
            'user' : os.getenv('TAP_POSTGRES_USER'),
            'default_replication_method' : self.FULL_TABLE,
            'filter_dbs' : 'dev'
        }
        if not original_properties:
            if self.default_replication_method is self.LOG_BASED:
                return_value['wal2json_message_format'] = '1'

            return_value['default_replication_method'] = self.default_replication_method

        return return_value

    def test_run(self):
        """Parametrized datatypes test running against each replication method."""

        self.default_replication_method = self.FULL_TABLE
        full_table_conn_id = connections.ensure_connection(self, original_properties=False)
        self.datatypes_test(full_table_conn_id)

        # TODO Parametrize tests to also run against multiple local (db) timezones
        # with db_utils.get_test_connection(test_db) as conn:
        #     conn.autocommit = True
        #     with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:

        #         db_utils.set_db_time_zone('America/New_York')


        # self.default_replication_method = self.INCREMENTAL
        # incremental_conn_id = connections.ensure_connection(self, original_properties=False)
        # self.datatypes_test(incremental_conn_id)

        # self.default_replication_method = self.LOG_BASED
        # log_based_conn_id = connections.ensure_connection(self, original_properties=False)
        # self.datatypes_test(log_based_conn_id)


    def datatypes_test(self, conn_id):
        """
        Test Description:
          Basic Datatypes Test for a database tap.

        Test Cases:

        """

        # run discovery (check mode)
        check_job_name = runner.run_check_mode(self, conn_id)

        # Verify check exit codes
        exit_status = menagerie.get_exit_status(conn_id, check_job_name)
        menagerie.verify_check_exit_status(self, exit_status, check_job_name)

        # Verify discovery generated a catalog
        found_catalogs = [found_catalog for found_catalog in menagerie.get_catalogs(conn_id)
                          if found_catalog['tap_stream_id'] in self.expected_check_stream_ids()]
        self.assertGreaterEqual(len(found_catalogs), 1)

        # Verify discovery generated the expected catalogs by name
        found_catalog_names = {catalog['stream_name'] for catalog in found_catalogs}
        self.assertSetEqual(self.expected_check_streams(), found_catalog_names)

        # verify that persisted streams have the correct properties
        test_catalog = found_catalogs[0]
        self.assertEqual(test_table_name, test_catalog['stream_name'])
        print("discovered streams are correct")

        # perform table selection
        print('selecting {} and all fields within the table'.format(test_table_name))
        schema_and_metadata = menagerie.get_annotated_schema(conn_id, test_catalog['stream_id'])
        # TODO need to enable multiple replication methods (see auto fields test)
        additional_md = [{ "breadcrumb" : [], "metadata" : {'replication-method' : self.default_replication_method}}]
        _ = connections.select_catalog_and_fields_via_metadata(conn_id, test_catalog, schema_and_metadata, additional_md)

        # run sync job 1 and verify exit codes
        sync_job_name = runner.run_sync_mode(self, conn_id)
        exit_status = menagerie.get_exit_status(conn_id, sync_job_name)
        menagerie.verify_sync_exit_status(self, exit_status, sync_job_name)

        # get records
        record_count_by_stream = runner.examine_target_output_file(
            self, conn_id, self.expected_sync_streams(), self.expected_primary_keys()
        )
        records_by_stream = runner.get_records_from_target_output()
        messages = records_by_stream[test_table_name]['messages']

        # verify the persisted schema matches expectations TODO NEED TO GO TRHOUGH SCHEMA MANUALLY STILL
        # self.assertEqual(expected_schema, records_by_stream[test_table_name]['schema'])

        # verify the number of records and number of messages match our expectations
        expected_record_count = len(self.expected_records)
        expected_message_count = expected_record_count + 2 # activate versions
        self.assertEqual(expected_record_count, record_count_by_stream[test_table_name])
        self.assertEqual(expected_message_count, len(messages))

        # verify we start and end syncs with an activate version message
        self.assertEqual('activate_version', messages[0]['action'])
        self.assertEqual('activate_version', messages[-1]['action'])

        # verify the remaining messages are upserts
        actions = {message['action'] for message in messages if message['action'] != 'activate_version'}
        self.assertSetEqual({'upsert'}, actions)


        # Each record was inserted with a specific test case in mind
        for test_case, message in zip(self.expected_records.keys(), messages[1:]):
            with self.subTest(test_case=test_case):

                # grab our expected record
                expected_record = self.expected_records[test_case]

                # Verify replicated records match our expectations
                for field in expected_record.keys():
                    with self.subTest(field=field):

                        # some data types require adjustments to actual values to make valid comparison...
                        if field == 'our_jsonb':
                            expected_field_value = expected_record.get(field, '{"MISSING": "FIELD"}')
                            actual_field_value = json.loads(message['data'].get(field, '{"MISSING": "FIELD"}'))

                            self.assertDictEqual(expected_field_value, actual_field_value)

                        # but most type do not
                        else:

                            expected_field_value = expected_record.get(field, "MISSING FIELD")
                            actual_field_value = message['data'].get(field, "MISSING FIELD")

                            self.assertEqual(expected_field_value, actual_field_value)


SCENARIOS.add(PostgresDatatypes)
