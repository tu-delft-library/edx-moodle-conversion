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
 * Admin page for managing video mappings
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

require_once(__DIR__ . '/../../config.php');
require_once($CFG->libdir . '/tablelib.php');
require_once($CFG->dirroot . '/filter/vidrouter/classes/form/edit_form.php');
require_once($CFG->dirroot . '/filter/vidrouter/classes/form/import_form.php');

use filter_vidrouter\bulk_import;

$action = optional_param('action', '', PARAM_ALPHA);
$id = optional_param('id', 0, PARAM_INT);
$export = optional_param('export', 0, PARAM_INT);
$delete = optional_param('delete', 0, PARAM_INT);
$confirm = optional_param('confirm', 0, PARAM_INT);

require_login();
require_capability('filter/vidrouter:manage', context_system::instance());

$PAGE->set_context(context_system::instance());
$PAGE->set_url(new moodle_url('/filter/vidrouter/manage.php'));
$PAGE->set_pagelayout('admin');
$PAGE->set_title(get_string('pluginname', 'filter_vidrouter'));

if ($delete) {
    if ($confirm) {
        require_sesskey();
        global $DB;
        $DB->delete_records('filter_vidrouter_map', array('id' => $delete));
        // Invalidate cach
        $cache = cache::make('filter_vidrouter', 'map');
        $cache->delete('all_videos');
        redirect($PAGE->url, get_string('deletemapping', 'filter_vidrouter') . ' ' . get_string('deleted', 'moodle'), notification::NOTIFY_SUCCESS);
    } else {
        echo $OUTPUT->header();
        echo $OUTPUT->confirm(
            get_string('confirmdeletemapping', 'filter_vidrouter'),
            new moodle_url($PAGE->url, array('delete' => $delete, 'confirm' => 1, 'sesskey' => sesskey())),
            $PAGE->url
        );
        echo $OUTPUT->footer();
        exit;
    }
}

if ($export) {
    require_sesskey();
    global $DB;
    $records = $DB->get_records('filter_vidrouter_map', array(), 'vidkey ASC');

    $data = array();
    foreach ($records as $record) {
        $data[] = (array)$record;
    }

    header('Content-Type: application/json');
    header('Content-Disposition: attachment; filename="video_mappings_' . date('YmdHis') . '.json"');
    echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($action == 'edit' || $action == 'add') {
    $mform = new filter_vidrouter_edit_form();

    if ($mform->is_cancelled()) {
        redirect($PAGE->url);
    } else if ($data = $mform->get_data()) {
        global $DB;

        $record = new stdClass();
        $record->vidkey = $data->vidkey;
        $record->youtubeid = $data->youtubeid ?? null;
        $record->edxvideoid = $data->edxvideoid ?? null;
        $record->tuddownloadid = $data->tuddownloadid ?? null;
        $record->stlbaseid = $data->stlbaseid ?? null;
        $record->urlname = $data->urlname ?? null;
        $record->courseid = $data->courseid ?? null;
        $record->title = $data->title ?? null;
        $record->videopagepath = $data->videopagepath ?? null;
        $record->timemodified = time();

        if ($action == 'edit' && $id) {
            $record->id = $id;
            $DB->update_record('filter_vidrouter_map', $record);
        } else {
            $record->timecreated = time();
            $DB->insert_record('filter_vidrouter_map', $record);
        }

        // Invalidate cache, important! 
        $cache = cache::make('filter_vidrouter', 'map');
        $cache->delete('all_videos');

        $msg = ($action == 'edit') ?
            get_string('editmapping', 'filter_vidrouter') . ' ' . get_string('updated', 'moodle') :
            get_string('addmapping', 'filter_vidrouter') . ' ' . get_string('added', 'moodle');
        redirect($PAGE->url, $msg, notification::NOTIFY_SUCCESS);
    } else {
        if ($action == 'edit' && $id) {
            global $DB;
            $record = $DB->get_record('filter_vidrouter_map', array('id' => $id), '*', MUST_EXIST);
            $mform->set_data($record);
        }

        echo $OUTPUT->header();
        echo $OUTPUT->heading(get_string($action == 'edit' ? 'editbuttontext' : 'addbuttontext', 'filter_vidrouter'));
        $mform->display();
        echo $OUTPUT->footer();
        exit;
    }
}

if ($action == 'import') {
    $importconfirm = optional_param('importconfirm', 0, PARAM_INT);

    if ($importconfirm) {
        require_sesskey();
        $matchfield = required_param('matchfield', PARAM_ALPHA);
        $csvdata = required_param('csvdata', PARAM_RAW);

        $parsed = bulk_import::parse_csv($csvdata);
        $plan = bulk_import::plan($parsed['rows'], $matchfield);
        $updated = bulk_import::apply($plan);
        $counts = array_count_values(array_column($plan, 'status'));

        $summary = get_string('import_summary', 'filter_vidrouter', (object)[
            'updated' => $updated,
            'unmatched' => $counts['unmatched'] ?? 0,
            'ambiguous' => $counts['ambiguous'] ?? 0,
        ]);
        redirect($PAGE->url, $summary, null, notification::NOTIFY_SUCCESS);
    }

    $mform = new filter_vidrouter_import_form();

    if ($mform->is_cancelled()) {
        redirect($PAGE->url);
    } else if ($data = $mform->get_data()) {
        $parsed = bulk_import::parse_csv($data->csvdata);
        $plan = bulk_import::plan($parsed['rows'], $data->matchfield);
        $matched = count(array_filter($plan, fn($e) => $e['status'] === 'matched'));

        echo $OUTPUT->header();
        echo $OUTPUT->heading(get_string('import_preview', 'filter_vidrouter'));

        $previewtable = new html_table();
        $previewtable->head = [
            get_string('import_matchfield', 'filter_vidrouter'),
            get_string('import_status', 'filter_vidrouter'),
            get_string('import_changes', 'filter_vidrouter'),
        ];
        foreach ($plan as $entry) {
            $changesstr = [];
            foreach ($entry['changes'] as $col => $val) {
                $changesstr[] = s($col) . ' = ' . s($val);
            }
            $previewtable->data[] = [
                s($entry['matchvalue']),
                get_string('import_status_' . $entry['status'], 'filter_vidrouter'),
                implode(', ', $changesstr),
            ];
        }
        echo html_writer::table($previewtable);

        $confirmattrs = ['type' => 'submit', 'class' => 'btn btn-primary'];
        if ($matched === 0) {
            $confirmattrs['disabled'] = 'disabled';
        }

        echo html_writer::start_tag('form', ['method' => 'post', 'action' => $PAGE->url]);
        echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'action', 'value' => 'import']);
        echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'importconfirm', 'value' => 1]);
        echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
        echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'matchfield', 'value' => $data->matchfield]);
        echo html_writer::tag('textarea', $data->csvdata, ['name' => 'csvdata', 'hidden' => 'hidden']);
        echo html_writer::tag('button', get_string('import_confirm', 'filter_vidrouter'), $confirmattrs);
        echo ' ';
        echo $OUTPUT->single_button($PAGE->url, get_string('cancel'), 'get');
        echo html_writer::end_tag('form');

        echo $OUTPUT->footer();
        exit;
    } else {
        echo $OUTPUT->header();
        echo $OUTPUT->heading(get_string('import_heading', 'filter_vidrouter'));
        $mform->display();
        echo $OUTPUT->footer();
        exit;
    }
}

// Show listings table and controls.
echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('manage', 'filter_vidrouter'));

// Add/Export/Import buttons
$addurl = new moodle_url($PAGE->url, array('action' => 'add'));
$exporturl = new moodle_url($PAGE->url, array('export' => 1, 'sesskey' => sesskey()));
$importurl = new moodle_url($PAGE->url, array('action' => 'import'));

echo '<div class="filter_vidrouter_controls">';
echo $OUTPUT->single_button($addurl, get_string('addbuttontext', 'filter_vidrouter'), 'get');
echo $OUTPUT->single_button($exporturl, get_string('export_json', 'filter_vidrouter'), 'get');
echo $OUTPUT->single_button($importurl, get_string('importbuttontext', 'filter_vidrouter'), 'get');
echo '</div>';

// Show table
global $DB;
$table = new flexible_table('filter_vidrouter_map');
$table->define_columns(array('vidkey', 'title', 'courseid', 'timemodified', 'actions'));
$table->define_headers(array(
    get_string('table_vidkey', 'filter_vidrouter'),
    get_string('table_title', 'filter_vidrouter'),
    get_string('table_courseid', 'filter_vidrouter'),
    get_string('table_timemodified', 'filter_vidrouter'),
    get_string('edit'),
));
$table->define_baseurl($PAGE->url);
$table->sortable(true, 'vidkey', SORT_ASC);
$table->collapsible(false);
$table->set_attribute('class', 'filter_vidrouter_table');

$table->setup();

$sql = 'SELECT id, vidkey, title, courseid, timemodified FROM {filter_vidrouter_map}';
$params = array();

if ($table->get_sql_sort()) {
    $sql .= ' ORDER BY ' . $table->get_sql_sort();
} else {
    $sql .= ' ORDER BY vidkey ASC';
}

$records = $DB->get_records_sql($sql, $params);

foreach ($records as $record) {
    $editurl = new moodle_url($PAGE->url, array('action' => 'edit', 'id' => $record->id));
    $deleteurl = new moodle_url($PAGE->url, array('delete' => $record->id));

    $editlink = html_writer::link($editurl, get_string('edit'));
    $deletelink = html_writer::link($deleteurl, get_string('delete'));

    $row = array(
        s($record->vidkey),
        s($record->title ?? '—'),
        s($record->courseid ?? '—'),
        userdate($record->timemodified, '%d %b %Y, %H:%M'),
        $editlink . ' | ' . $deletelink,
    );
    $table->add_data($row);
}

$table->print_html();

echo $OUTPUT->footer();
