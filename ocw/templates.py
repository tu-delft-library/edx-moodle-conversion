MOODLE_BACKUP = """\
<?xml version="1.0" encoding="UTF-8"?>
<moodle_backup>
  <information>
    <name>{course_name}</name>
    <moodle_version>{moodle_version}</moodle_version>
    <original_course_id>1</original_course_id>
    <original_course_fullname>{course_name}</original_course_fullname>
    <original_course_shortname>{course_id}</original_course_shortname>
    <original_course_startdate>{ts}</original_course_startdate>
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
  </information>
</moodle_backup>"""

COURSE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<course id="1">
  <shortname>{course_id}</shortname>
  <fullname>{course_name}</fullname>
  <startdate>{ts}</startdate>
  <enddate>0</enddate>
  <visible>1</visible>
</course>"""

SECTION_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<section id="{id}">
  <number>{number}</number>
  <name>{name}</name>
  <summary/>
  <summaryformat>1</summaryformat>
  <visible>1</visible>
  <sequence>{sequence}</sequence>
</section>"""

PAGE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<activity id="{id}" moduleid="{id}" modulename="page" contextid="{ctx}">
  <page id="{id}">
    <name>{name}</name>
    <intro/>
    <introformat>1</introformat>
    <content>{content}</content>
    <contentformat>1</contentformat>
    <displayoptions>a:0:{{}}</displayoptions>
    <timemodified>{ts}</timemodified>
  </page>
</activity>"""

FILE_ENTRY = (
    '  <file id="{id}"><contenthash>{sha1}</contenthash>'
    '<contextid>1</contextid><component>mod_page</component>'
    '<filearea>content</filearea><itemid>0</itemid>'
    '<filepath>/</filepath><filename>{name}</filename>'
    '<filesize>{size}</filesize><mimetype>{mime}</mimetype>'
    '<status>0</status><timecreated>{ts}</timecreated>'
    '<timemodified>{ts}</timemodified><sortorder>0</sortorder>'
    '<userid>2</userid><repositorytype>$@NULL@$</repositorytype>'
    '<repositoryid>$@NULL@$</repositoryid><reference>$@NULL@$</reference></file>'
)
