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
    private const SHORTCODE = '/\[\[vid:([A-Za-z0-9_\-]+)\]\]/';

    #[\Override]
    public function filter($text, array $options = [])
    {
        if (!is_string($text) || empty($text)) {
            return $text;
        }

        if (!preg_match_all(self::SHORTCODE, $text, $found)) {
            return $text;
        }

        $keymap = $this->lookup(array_unique($found[1]));
        $overrides = video_renderer::overrides_for($this->context);

        $text = preg_replace_callback(
            self::SHORTCODE,
            function ($matches) use ($keymap, $overrides) {
                $vidkey = $matches[1];

                if (isset($keymap[$vidkey])) {
                    return video_renderer::render($keymap[$vidkey], $overrides);
                } else {
                    return video_renderer::render_unavailable();
                }
            },
            $text
        );

        return $text;
    }

    /**
     * @param string[] $keys distinct vidkeys
     * @return \stdClass[] mapping rows keyed by vidkey, unknown keys absent
     */
    private function lookup(array $keys): array
    {
        global $DB;

        $cache = \cache::make('filter_vidrouter', 'map');
        $rows = array_filter($cache->get_many($keys));
        $missing = array_diff($keys, array_keys($rows));

        if ($missing) {
            $fresh = [];
            foreach ($DB->get_records_list('filter_vidrouter_map', 'vidkey', $missing) as $row) {
                $fresh[$row->vidkey] = $row;
            }
            $cache->set_many($fresh);
            $rows += $fresh;
        }

        return $rows;
    }
}
