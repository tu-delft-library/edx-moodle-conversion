MOODLE_BACKUP = """\
<?xml version="1.0" encoding="UTF-8"?>
<moodle_backup>
  <information>
    <name>{course_name}</name>
    <moodle_version>{moodle_version}</moodle_version>
    <moodle_release>{moodle_version}</moodle_release>
    <backup_version>{moodle_version}</backup_version>
    <backup_release>4.5</backup_release>
    <backup_date>{ts}</backup_date>
    <mnet_remoteusers>0</mnet_remoteusers>
    <include_files>1</include_files>
    <include_file_references_to_external_content>0</include_file_references_to_external_content>
    <original_wwwroot>http://localhost</original_wwwroot>
    <original_site_identifier_hash>0</original_site_identifier_hash>
    <original_course_id>1</original_course_id>
    <original_course_format>topics</original_course_format>
    <original_course_fullname>{course_name}</original_course_fullname>
    <original_course_shortname>{course_id}</original_course_shortname>
    <original_course_startdate>{ts}</original_course_startdate>
    <original_course_enddate>0</original_course_enddate>
    <original_course_contextid>1</original_course_contextid>
    <original_system_contextid>1</original_system_contextid>
    <details>
      <detail backup_id="0">
        <type>course</type>
        <format>moodle2</format>
        <interactive>1</interactive>
        <mode>10</mode>
        <execution>1</execution>
        <executiontime>0</executiontime>
      </detail>
    </details>
    <contents>
      <activities>
{acts}
      </activities>
      <sections>
{secs}
      </sections>
      <course>
        <courseid>1</courseid>
        <title>{course_name}</title>
        <directory>course</directory>
      </course>
    </contents>
    <settings>
{settings}
    </settings>
  </information>
</moodle_backup>"""

MODULE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<module id="{id}" version="{moodle_version}">
  <modulename>page</modulename>
  <sectionid>{sec_id}</sectionid>
  <sectionnumber>{sec_num}</sectionnumber>
  <idnumber></idnumber>
  <added>{ts}</added>
  <score>0</score>
  <indent>0</indent>
  <visible>1</visible>
  <visibleoncoursepage>1</visibleoncoursepage>
  <visibleold>1</visibleold>
  <groupmode>0</groupmode>
  <groupingid>0</groupingid>
  <completion>0</completion>
  <completiongradeitemnumber>$@NULL@$</completiongradeitemnumber>
  <completionpassgrade>0</completionpassgrade>
  <completionview>0</completionview>
  <completionexpected>0</completionexpected>
  <availability>$@NULL@$</availability>
  <showdescription>0</showdescription>
  <tags/>
</module>"""

ROLES_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<roles_definition/>'

GRADEBOOK_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<gradebook>
  <attributes/>
  <grade_categories/>
  <grade_items/>
  <grade_letters/>
  <grade_settings/>
</gradebook>"""

GRADE_HISTORY_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<grade_history>\n  <grade_grades/>\n</grade_history>'

GROUPS_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<groups>\n  <groupings/>\n</groups>'

OUTCOMES_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<outcomes_definition/>'

QUESTIONS_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<question_categories/>'

SCALES_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<scales_definition/>'

COURSE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<course id="1" contextid="1">
  <shortname>{course_id}</shortname>
  <fullname>{course_name}</fullname>
  <idnumber></idnumber>
  <summary></summary>
  <summaryformat>1</summaryformat>
  <format>topics</format>
  <showgrades>1</showgrades>
  <newsitems>5</newsitems>
  <startdate>{ts}</startdate>
  <enddate>0</enddate>
  <marker>0</marker>
  <maxbytes>0</maxbytes>
  <legacyfiles>0</legacyfiles>
  <showreports>0</showreports>
  <visible>1</visible>
  <groupmode>0</groupmode>
  <groupmodeforce>0</groupmodeforce>
  <defaultgroupingid>0</defaultgroupingid>
  <lang></lang>
  <theme></theme>
  <timecreated>{ts}</timecreated>
  <timemodified>{ts}</timemodified>
  <requested>0</requested>
  <enablecompletion>0</enablecompletion>
  <completionnotify>0</completionnotify>
  <hiddensections>0</hiddensections>
  <coursedisplay>0</coursedisplay>
  <category id="1">
    <name>Miscellaneous</name>
    <description></description>
  </category>
  <tags/>
  <customfields/>
</course>"""

SECTION_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<section id="{id}">
  <number>{number}</number>
  <name>{name}</name>
  <summary/>
  <summaryformat>1</summaryformat>
  <sequence>{sequence}</sequence>
  <visible>1</visible>
  <availabilityjson>$@NULL@$</availabilityjson>
  <timemodified>{ts}</timemodified>
</section>"""

COURSE_ROLES_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<roles>\n  <role_overrides/>\n  <role_assignments/>\n</roles>'
COURSE_FILTERS_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<filters>\n  <filter_actives/>\n  <filter_configs/>\n</filters>'
COURSE_INFOREF_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>'
COURSE_COMPLETION_DEFAULTS_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<course_completion_defaults/>'
COURSE_ENROLMENTS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<enrolments>
  <enrols>
    <enrol id="1">
      <enrol>manual</enrol>
      <status>0</status>
      <name>$@NULL@$</name>
      <enrolperiod>0</enrolperiod>
      <enrolstartdate>0</enrolstartdate>
      <enrolenddate>0</enrolenddate>
      <expirynotify>0</expirynotify>
      <expirythreshold>86400</expirythreshold>
      <notifyall>0</notifyall>
      <password>$@NULL@$</password>
      <cost>$@NULL@$</cost>
      <currency>$@NULL@$</currency>
      <role>0</role>
      <customint1>$@NULL@$</customint1>
      <customint2>$@NULL@$</customint2>
      <customint3>$@NULL@$</customint3>
      <customint4>$@NULL@$</customint4>
      <customint5>$@NULL@$</customint5>
      <customint6>$@NULL@$</customint6>
      <customint7>$@NULL@$</customint7>
      <customint8>$@NULL@$</customint8>
      <customchar1>$@NULL@$</customchar1>
      <customchar2>$@NULL@$</customchar2>
      <customchar3>$@NULL@$</customchar3>
      <customdec1>$@NULL@$</customdec1>
      <customdec2>$@NULL@$</customdec2>
      <customtext1>$@NULL@$</customtext1>
      <customtext2>$@NULL@$</customtext2>
      <customtext3>$@NULL@$</customtext3>
      <customtext4>$@NULL@$</customtext4>
      <timecreated>{ts}</timecreated>
      <timemodified>{ts}</timemodified>
      <userinstances/>
    </enrol>
  </enrols>
</enrolments>"""

ACTIVITY_GRADES_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<activity_gradebook/>'
ACTIVITY_GRADE_HISTORY_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<grade_history/>'
ACTIVITY_ROLES_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<roles/>'
ACTIVITY_FILTERS_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<filters/>'

PAGE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<activity id="{id}" moduleid="{id}" modulename="page" contextid="{ctx}">
  <page id="{id}">
    <name>{name}</name>
    <intro/>
    <introformat>1</introformat>
    <content>{content}</content>
    <contentformat>1</contentformat>
    <legacyfiles>0</legacyfiles>
    <legacyfileslast>$@NULL@$</legacyfileslast>
    <display>5</display>
    <displayoptions>a:1:{{s:10:"printintro";s:1:"0";}}</displayoptions>
    <revision>2</revision>
    <timemodified>{ts}</timemodified>
  </page>
</activity>"""

FILE_ENTRY = (
    '  <file id="{id}"><contenthash>{sha1}</contenthash>'
    '<contextid>{ctx}</contextid><component>mod_page</component>'
    '<filearea>content</filearea><itemid>0</itemid>'
    '<filepath>/</filepath><filename>{name}</filename>'
    '<filesize>{size}</filesize><mimetype>{mime}</mimetype>'
    '<status>0</status><timecreated>{ts}</timecreated>'
    '<timemodified>{ts}</timemodified><sortorder>0</sortorder>'
    '<userid>2</userid><repositorytype>$@NULL@$</repositorytype>'
    '<repositoryid>$@NULL@$</repositoryid>'
    '<source>$@NULL@$</source><author>$@NULL@$</author>'
    '<license>allrightsreserved</license>'
    '<reference>$@NULL@$</reference></file>'
)
