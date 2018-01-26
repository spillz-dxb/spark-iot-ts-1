from au.com.gegroup.ts.metadata.es_metadata import ESMetadata
from au.com.gegroup.ts.reader import Reader
from au.com.gegroup.haystack import to_sql_parser


__author__ = 'topsykretts'


class IOTHistoryReader(Reader):
    """
    This class is abstraction for reading Flint TS dataframe based on metadata and date filter.
    A new instance of this class should be created for a pair of filo_dataset and load_filter.
    Eg: filo_dataset = 'iot_history_v0' and load_filter = "siteRef = 'Site'" creates reader for
    dataset 'iot_history_v0' for site 'Site'.
    Load filter is None by default.
    """

    def __init__(self, sqlContext, dataset, view_name, rule_on=None, site_filter=None):
        """
        constructor for Reader object to read from filodb
        :param sqlContext: current spark's sqlContext
        :param dataset: the filodb dataset name or dataframe that should be loaded
        :param view_name: the name to temp table, that will be used in constructed queries
        :param site_filter: haystack format filter string of equipment level. Eg: 'equip and boiler'
        :param site_filter: haystack format filter string of site level. Directly applied to history. Eg: 'siteRef == "Site"'
        :return: Reader object
        """
        if site_filter is not None:
            site_filter = to_sql_parser.parse(site_filter)
        super().__init__(sqlContext, dataset, view_name, site_filter)
        self._set_metadata()
        self._rule_on = None
        self.handle_rule_on(rule_on)

    def handle_rule_on(self, rule_on):
        if rule_on is not None:
            rule_on = to_sql_parser.parse(rule_on)
            equip_query = "select equipRef from metadata where " + rule_on
            # print("Rule on query = ", equip_query)
            rows = self._sqlContext.sql(equip_query).collect()
            equip_refs = []
            for row in rows:
                equip_refs.append("'" + row[0] + "'")
            if len(equip_refs) > 0:
                self._rule_on = "equipRef in (" + ",".join(equip_refs) + ")"
            else:
                self._rule_on = "false"
                print("Rule on didn't match with any records..")
            # print(self._rule_on)


    def _set_metadata(self):
        self._metadata_df = ESMetadata.getInstance(self._sqlContext)
        # self._metadata_df.cache()
        self._metadata_df.createOrReplaceTempView("metadata")

    def metadata(self, metadata):
        """
        builder that initializes meta tags to be filtered.
        :param metadata: tags to be filtered like "supply and water and temp and sensor"
        :return: reader object with tag_filter initialized
        """
        sql = to_sql_parser.parse(metadata)
        tag_query = " select dis from metadata where dis IS NOT NULL and " + sql
        if self._rule_on is not None:
            tag_query += " and " + self._rule_on
        rows = self._sqlContext.sql(tag_query).collect()
        point_names = []

        for row in rows:
            point_names.append("'" + row[0] + "'")
        if len(point_names) > 0:
            self._tag_filter = "pointName in (" + ",".join(point_names) + ")"
        else:
            self._tag_filter = "false"
        return self

    def get_metadata_df(self):
        return self._metadata_df
