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
 * Backup hook for local_vidrouter.
 *
 * For every [[vid:KEY]] shortcode actually present in the course being backed up, resolves the
 * matching filter_vidrouter_map row to its export-time markup via
 * filter_vidrouter\video_renderer::render_for_export() (governed by the 'embedstyle' setting,
 * independently of what's shown live on the site) and embeds that as an html child element on
 * the <video> record, alongside the raw source ids. restore_local_vidrouter_plugin::
 * after_restore_course() then freezes that html into the duplicated course's pages, in place of
 * [[vid:KEY]].
 *
 * @package    local_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

class backup_local_vidrouter_plugin extends backup_local_plugin {
    /**
     * Define the course plugin structure
     *
     * Builds one <video> element per vidkey actually used in this course, each carrying
     * the raw source ids plus a resolved html field with the actual rendered markup.
     */
    protected function define_course_plugin_structure() {
        $plugin = $this->get_plugin_element();
        $pluginwrapper = new backup_nested_element($this->get_recommended_name());
        $plugin->add_child($pluginwrapper);

        $video = new backup_nested_element('video', null, [
            'vidkey', 'title', 'youtubeid', 'edxvideoid', 'tuddownloadid', 'collegeramaid',
            'srtbaseid', 'urlname', 'videopagepath', 'html',
        ]);
        $pluginwrapper->add_child($video);

        $video->set_source_array($this->get_video_rows());
    }

    /**
     * Fetch the video mapping rows for vidkeys actually referenced in this course's pages,
     * each with its html field already resolved.
     *
     * @return array[] one row per video, keyed by the <video> element's field names
     */
    private function get_video_rows(): array {
        global $DB;

        $courseid = $this->task->get_courseid();
        $pages = $DB->get_records('page', ['course' => $courseid], '', 'id, content');

        $vidkeys = [];
        foreach ($pages as $page) {
            if (preg_match_all('/\[\[vid:([A-Za-z0-9_\-]+)\]\]/', (string) $page->content, $matches)) {
                foreach ($matches[1] as $vidkey) {
                    $vidkeys[$vidkey] = true;
                }
            }
        }

        if (empty($vidkeys)) {
            return [];
        }

        $records = $DB->get_records_list('filter_vidrouter_map', 'vidkey', array_keys($vidkeys));

        $rows = [];
        foreach ($records as $record) {
            $rows[] = [
                'vidkey' => $record->vidkey,
                'title' => $record->title,
                'youtubeid' => $record->youtubeid,
                'edxvideoid' => $record->edxvideoid,
                'tuddownloadid' => $record->tuddownloadid,
                'collegeramaid' => $record->collegeramaid,
                'srtbaseid' => $record->srtbaseid,
                'urlname' => $record->urlname,
                'videopagepath' => $record->videopagepath,
                'html' => \filter_vidrouter\video_renderer::render_for_export($record),
            ];
        }

        return $rows;
    }
}
