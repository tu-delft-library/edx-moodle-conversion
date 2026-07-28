<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <http://www.gnu.org/licenses/>.

/**
 * Language strings for filter_vidrouter
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Video Router Filter';
$string['filtername'] = 'Video Router Filter';

$string['manage'] = 'Manage video mappings';
$string['managedesc'] = 'Manage the mappings between video shortcodes and their sources (YouTube, edX, TU Delft).';

$string['capability:manage'] = 'Manage video routes and mappings';

$string['table_vidkey'] = 'Video Key';
$string['table_title'] = 'Title';
$string['table_courseid'] = 'Course ID';
$string['table_timemodified'] = 'Last Modified';

$string['form_vidkey'] = 'Video Key';
$string['form_vidkey_help'] = 'Unique identifier for this video. Used in the [[vid:KEY]] shortcode.';
$string['form_title'] = 'Title';
$string['form_title_help'] = 'Display name of the video (e.g. the unit display_name).';
$string['form_courseid'] = 'Course ID';
$string['form_courseid_help'] = 'OLX course/run identifier that this video came from.';
$string['form_urlname'] = 'URL Name';
$string['form_urlname_help'] = 'OLX unit url_name (internal filename/slug).';
$string['form_youtubeid'] = 'YouTube ID';
$string['form_youtubeid_help'] = 'YouTube video ID (optional). 11-character code or full URL.';
$string['form_edxvideoid'] = 'edX Video ID';
$string['form_edxvideoid_help'] = 'edX CDN UUID (optional). Used as join key for transcripts.';
$string['form_tuddownloadid'] = 'TU Delft Download ID';
$string['form_tuddownloadid_help'] = 'TU Delft data-downloadid path or URL (optional).';
$string['form_stlbaseid'] = 'STL Base ID';
$string['form_stlbaseid_help'] = 'STL file base URL (optional, unverified).';
$string['form_videopagepath'] = 'Video Page Path';
$string['form_videopagepath_help'] = 'Path in course structure: "Chapter > Subsection > Unit". Populated at migration time.';

$string['addbuttontext'] = 'Add video mapping';
$string['editbuttontext'] = 'Edit mapping';
$string['savebuttontext'] = 'Save mapping';
$string['deletebuttontext'] = 'Delete mapping';

$string['export_json'] = 'Export as JSON';
$string['export_json_desc'] = 'Download all mappings as a JSON file.';

$string['importbuttontext'] = 'Bulk import';
$string['import_heading'] = 'Bulk-assign values to existing mappings';
$string['import_matchfield'] = 'Match on';
$string['import_matchfield_help'] = 'Existing rows are looked up by this field. Only rows with exactly one match are updated.';
$string['import_csvdata'] = 'CSV data';
$string['import_csvdata_help'] = 'Paste CSV with a header row. The header must be made up of field names (e.g. youtubeid,edxvideoid). The "Match on" column\'s value is used to find the existing row; every other column present is written onto it. Existing values are only overwritten for columns you include — blank cells are left untouched.';
$string['import_preview'] = 'Preview';
$string['import_confirm'] = 'Apply changes';
$string['import_status'] = 'Result';
$string['import_changes'] = 'Changes';
$string['import_status_matched'] = 'Will update';
$string['import_status_unmatched'] = 'No matching row — skipped';
$string['import_status_ambiguous'] = 'Matches more than one row — skipped';
$string['import_status_invalid'] = 'Missing match value — skipped';
$string['import_status_nochange'] = 'Matched, but no columns to change — skipped';
$string['import_summary'] = '{$a->updated} row(s) updated, {$a->unmatched} unmatched, {$a->ambiguous} ambiguous.';
$string['import_error_empty'] = 'No CSV data was provided.';
$string['import_error_unknown_column'] = 'Unknown column name: "{$a}". Valid columns are: vidkey, youtubeid, edxvideoid, tuddownloadid, stlbaseid, urlname, courseid, title, videopagepath.';
$string['import_error_duplicate_column'] = 'The header row contains the same column more than once.';

$string['video_unavailable'] = 'Video unavailable. Please contact your course team.';
$string['videourlmissing'] = '(video link missing)';

$string['primarysource'] = 'Primary video source';
$string['primarysource_desc'] = 'Which source field to render a video link from. Only sources with real, working implementations are listed here — edX and TU Delft download IDs are intentionally excluded (see project findings).';
$string['source_youtube'] = 'YouTube';

$string['embedstyle'] = 'Export embed style';
$string['embedstyle_desc'] = 'How to render videos in the HTML baked into a course backup/export (used when duplicating or restoring a course) — independent of how videos render live on the site, which always uses the native YouTube iframe for captions. "Video" outputs a plain link and lets Moodle\'s media filter embed it (matches how OLX-exported videos were originally rendered), but YouTube captions are not available in that mode. "Iframe" matches the live rendering, with working captions.';
$string['embedstyle_video'] = 'Video (matches OLX export, no captions)';
$string['embedstyle_iframe'] = 'Iframe (matches live rendering, with captions)';

$string['addmapping'] = 'Add mapping';
$string['editmapping'] = 'Edit mapping';
$string['deletemapping'] = 'Delete mapping';
$string['confirmdeletemapping'] = 'Are you sure you want to delete this video mapping?';

$string['error_invalid_vidkey'] = 'Invalid video key. Must contain only alphanumeric characters, dashes, and underscores.';
$string['error_duplicate_vidkey'] = 'A video mapping with this key already exists.';

$string['messageprovider:notifyadmin'] = 'Admin notifications';
