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

namespace filter_vidrouter;

/**
 * Render-time filter for video shortcodes.
 *
 * Replaces [[vid:KEY]] shortcodes with video markup or placeholder.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class text_filter extends \core_filters\text_filter
{
    #[\Override]
    public function filter($text, array $options = [])
    {
        if (!is_string($text) || empty($text)) {
            return $text;
        }

        $cache = \cache::make('filter_vidrouter', 'map');
        $videomaps = $cache->get('all_videos');

        if ($videomaps === false) {
            global $DB;
            $videomaps = $DB->get_records('filter_vidrouter_map');
            if ($videomaps === false) {
                $videomaps = array();
            }
            $cache->set('all_videos', $videomaps);
        }

        $keymap = array();
        foreach ($videomaps as $record) {
            $keymap[$record->vidkey] = $record;
        }

        $text = preg_replace_callback(
            '/\[\[vid:([A-Za-z0-9_\-]+)\]\]/',
            function ($matches) use ($keymap) {
                $vidkey = $matches[1];

                if (isset($keymap[$vidkey])) {
                    return video_renderer::render($keymap[$vidkey]);
                } else {
                    return video_renderer::render_unavailable();
                }
            },
            $text
        );

        return $text;
    }
}
