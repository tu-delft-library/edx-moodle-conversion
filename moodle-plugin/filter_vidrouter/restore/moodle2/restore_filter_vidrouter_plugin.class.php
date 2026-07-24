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
 * Restore hook for filter_vidrouter
 *
 * Handles two restore paths:
 * 1. Import-time: populates filter_vidrouter_map from migrated course XML
 * 2. Native backup-restore: replaces shortcodes with frozen HTML
 *
 * @package    filter_vidrouter
 * @copyright  2024 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

class restore_filter_vidrouter_plugin extends restore_course_plugin {
    /**
     * Define the course plugin structure
     *
     * Expects <video> elements per row, with attributes:
     * - vidkey (required)
     * - title, youtubeid, edxvideoid, tuddownloadid, stlbaseid, urlname, videopagepath (optional)
     * - html (optional, for frozen HTML from backup side)
     *
     * @return array of restore_path_element
     */
    protected function define_course_plugin_structure() {
        $paths = array();

        $paths[] = new restore_path_element(
            'plugin_filter_vidrouter_course',
            $this->get_pathfor('/plugin_filter_vidrouter_course')
        );

        $paths[] = new restore_path_element(
            'plugin_filter_vidrouter_video',
            $this->get_pathfor('/plugin_filter_vidrouter_course/video')
        );

        return $paths;
    }

    /**
     * Process a video element
     *
     * Inserts a row into filter_vidrouter_map with the current courseid from the restore context.
     *
     * @param array $data decoded element data
     */
    public function process_plugin_filter_vidrouter_video($data) {
        global $DB;

        $data = (object)$data;

        // Ensure vidkey is always present.
        if (empty($data->vidkey)) {
            return;
        }

        // Create the mapping record, always filling courseid from the restore context
        // (never trusting the XML value, which may be from a different course).
        $record = new stdClass();
        $record->vidkey = $data->vidkey;
        $record->title = $data->title ?? null;
        $record->youtubeid = $data->youtubeid ?? null;
        $record->edxvideoid = $data->edxvideoid ?? null;
        $record->tuddownloadid = $data->tuddownloadid ?? null;
        $record->stlbaseid = $data->stlbaseid ?? null;
        $record->urlname = $data->urlname ?? null;
        $record->videopagepath = $data->videopagepath ?? null;
        $record->courseid = $this->get_courseid();
        $record->timecreated = time();
        $record->timemodified = time();

        $newid = $DB->insert_record('filter_vidrouter_map', $record);

        // Store the vidkey→newid mapping for later reference if needed.
        $this->set_mapping('filter_vidrouter_video', $data->vidkey, $newid);
    }

    /**
     * Executed after the entire course restore is complete
     *
     * For native backup/restore (option 2 from the spec):
     * Scans restored page bodies for [[vid:KEY]] shortcodes.
     * If the backup contained frozen HTML (html attribute), replace the shortcode with it.
     * This freezes the video indirection and makes the duplicate self-contained.
     *
     * @return void
     */
    public function after_restore_course() {
        global $DB;

        // Retrieve the backup data to check for frozen HTML.
        $data = $this->connectionpoint->get_data();

        if (empty($data) || empty($data['tags'])) {
            return;
        }

        // Build a map of vidkey → frozen HTML from the backup.
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

        // Scan all page activities in the restored course.
        $courseid = $this->get_courseid();
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
                    // No frozen HTML → leave shortcode as-is (will degrade to placeholder).
                    return $matches[0];
                },
                $newcontent
            );

            // Update the page if any replacements were made.
            if ($updated) {
                $page->content = $newcontent;
                $page->timemodified = time();
                $DB->update_record('page', $page);
            }
        }
    }
}
