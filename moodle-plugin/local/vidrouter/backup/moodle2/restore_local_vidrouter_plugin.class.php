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
 * Restore hook for local_vidrouter. Runs during a RESTORE
 * (either an OLX import or a native Moodle course duplicate/restore), never during
 * backup creation itself.
 *
 * Handles two restore-time paths:
 * 1. Import-time: process_plugin_local_vidrouter_video() populates filter_vidrouter_map
 *    from migrated course XML.
 * 2. Native course duplicate/restore: after_restore_course() applies frozen HTML that the
 *    backup_local_vidrouter_plugin generates when backup gets started. 
 *    This is retrieved from the filter_vidrouter_map record and settings.
 *
 * @package    local_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

class restore_local_vidrouter_plugin extends restore_local_plugin
{
    public function __construct($plugintype, $pluginname, $step)
    {
        parent::__construct($plugintype, $pluginname, $step);
        error_log('[vidrouter] restore_local_vidrouter_plugin constructed, connectionpoint pending');
    }

    /**
     * Define the course plugin structure
     *
     * Expects <video> elements per row, with child elements.
     * - vidkey (required)
     * - title, youtubeid, edxvideoid, tuddownloadid, stlbaseid, urlname, videopagepath (optional)
     * - html (optional, for frozen HTML from backup side)
     *
     * @return array of restore_path_element
     */
    protected function define_course_plugin_structure()
    {
        $paths = array();

        $path = $this->get_pathfor('/video');
        error_log('[vidrouter] define_course_plugin_structure registering path: ' . $path);
        $paths[] = new restore_path_element(
            'plugin_local_vidrouter_video',
            $path
        );

        return $paths;
    }

    /**
     * Process a video element
     *
     * Inserts a row into filter_vidrouter_map for a vidkey seen for the first time, with
     * courseid set to this restore's target course. If the vidkey already has a row (this is
     * a duplicate/restore of a course whose videos were already mapped elsewhere), that
     * existing row is left untouched — courseid always names whichever course first created
     * the mapping, never the most recently restored/duplicated one. See
     * backup_local_vidrouter_plugin::get_video_rows() for why backup doesn't rely on courseid
     * to decide which videos belong to a course.
     *
     * @param array $data decoded element data
     */
    public function process_plugin_local_vidrouter_video($data)
    {
        global $DB;

        $data = (object)$data;
        error_log('[vidrouter] process_plugin_local_vidrouter_video fired, vidkey=' . ($data->vidkey ?? '(missing)'));

        if (empty($data->vidkey)) {
            return;
        }

        $existing = $DB->get_record('filter_vidrouter_map', array('vidkey' => $data->vidkey));
        if ($existing) {
            return;
        }

        $record = new stdClass();
        $record->vidkey = $data->vidkey;
        $record->title = $data->title ?? null;
        $record->youtubeid = $data->youtubeid ?? null;
        $record->edxvideoid = $data->edxvideoid ?? null;
        $record->tuddownloadid = $data->tuddownloadid ?? null;
        $record->stlbaseid = $data->stlbaseid ?? null;
        $record->urlname = $data->urlname ?? null;
        $record->videopagepath = $data->videopagepath ?? null;
        $record->courseid = $this->get_task()->get_courseid();
        $record->timecreated = time();
        $record->timemodified = $record->timecreated;

        $DB->insert_record('filter_vidrouter_map', $record);

        \cache::make('filter_vidrouter', 'map')->delete('all_videos');
    }

    /**
     * Restore-side half of native course duplicate/restore support. Runs once, after this
     * course's restore has fully completed.
     *
     * @return void
     */
    public function after_restore_course()
    {
        global $DB;

        $data = $this->connectionpoint->get_data();

        if (empty($data) || empty($data['tags'])) {
            return;
        }

        $frozenmap = array();
        if (isset($data['tags']['video']) && is_array($data['tags']['video'])) {
            foreach ($data['tags']['video'] as $videodata) {
                if (isset($videodata['attrs']['vidkey']) && isset($videodata['attrs']['html'])) {
                    $frozenmap[$videodata['attrs']['vidkey']] = $videodata['attrs']['html'];
                }
            }
        }

        if (empty($frozenmap)) {
            return;
        }

        $courseid = $this->get_task()->get_courseid();
        $pages = $DB->get_records('page', array('course' => $courseid));

        foreach ($pages as $page) {
            $updated = false;
            $newcontent = $page->content;

            // Replace each [[vid:KEY]] shortcode with frozen HTML if available.
            $newcontent = preg_replace_callback(
                '/\[\[vid:([A-Za-z0-9_\-]+)\]\]/',
                function ($matches) use ($frozenmap, &$updated) {
                    $vidkey = $matches[1];
                    if (isset($frozenmap[$vidkey])) {
                        $updated = true;
                        return $frozenmap[$vidkey];
                    }
                    return $matches[0];
                },
                $newcontent
            );

            if ($updated) {
                $page->content = $newcontent;
                $page->timemodified = time();
                $DB->update_record('page', $page);
            }
        }
    }
}
