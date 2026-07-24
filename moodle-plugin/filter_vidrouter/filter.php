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
 * Render-time filter for video shortcodes
 *
 * Replaces [[vid:KEY]] shortcodes with video markup or placeholder.
 *
 * @package    filter_vidrouter
 * @copyright  2024 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

class filter_vidrouter extends moodle_text_filter {
    /**
     * Apply the filter to the given text
     *
     * @param string $text the text to filter
     * @param array $options options array
     * @return string filtered text
     */
    public function filter($text, array $options = array()) {
        if (!is_string($text) || empty($text)) {
            return $text;
        }

        // Load the full video mapping table into request-scoped cache.
        $cache = cache::make('filter_vidrouter', 'map');
        $videomaps = $cache->get('all_videos');

        if ($videomaps === false) {
            global $DB;
            $videomaps = $DB->get_records('filter_vidrouter_map');
            if ($videomaps === false) {
                $videomaps = array();
            }
            $cache->set('all_videos', $videomaps);
        }

        // Build a quick-lookup map by vidkey.
        $keymap = array();
        foreach ($videomaps as $record) {
            $keymap[$record->vidkey] = $record;
        }

        // Find and replace all [[vid:KEY]] shortcodes.
        $text = preg_replace_callback(
            '/\[\[vid:([A-Za-z0-9_\-]+)\]\]/',
            function ($matches) use ($keymap) {
                $vidkey = $matches[1];

                if (isset($keymap[$vidkey])) {
                    $record = $keymap[$vidkey];
                    // **Decision point: which source to render is deferred.**
                    // For now, render a generic video placeholder with available ids.
                    // The custom video tag logic that decides youtube vs edx vs tud
                    // is a separate concern, not implemented here.
                    return $this->render_video_markup($record);
                } else {
                    // No mapping found → show placeholder.
                    return $this->render_unavailable_placeholder();
                }
            },
            $text
        );

        return $text;
    }

    /**
     * Render video markup
     *
     * Placeholder: shows available source IDs. Actual embed selection is deferred.
     *
     * @param stdClass $record the video mapping record
     * @return string HTML markup
     */
    private function render_video_markup($record) {
        $html = '<div class="filter_vidrouter_video" data-vidkey="' . s($record->vidkey) . '">';
        $html .= '<p><strong>' . s($record->title ?? 'Video') . '</strong></p>';

        // Show available sources (placeholder).
        $html .= '<div class="filter_vidrouter_sources">';
        if (!empty($record->youtubeid)) {
            $html .= '<p>YouTube: <code>' . s($record->youtubeid) . '</code></p>';
        }
        if (!empty($record->edxvideoid)) {
            $html .= '<p>edX: <code>' . s($record->edxvideoid) . '</code></p>';
        }
        if (!empty($record->tuddownloadid)) {
            $html .= '<p>TU Delft: <code>' . s($record->tuddownloadid) . '</code></p>';
        }
        $html .= '</div>';
        $html .= '</div>';

        return $html;
    }

    /**
     * Render unavailable placeholder
     *
     * @return string HTML markup
     */
    private function render_unavailable_placeholder() {
        return '<div class="filter_vidrouter_unavailable">' .
               '<p>' . get_string('video_unavailable', 'filter_vidrouter') . '</p>' .
               '</div>';
    }
}
