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
 * Resolves a filter_vidrouter_map row into video markup defined in the plugin settings.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class video_renderer
{
    /**
     * Render a video mapping record into its live, on-site markup.
     *
     * Used by text_filter on every page view. Always renders the native YouTube iframe (for
     * captions). 
     *
     * @param \stdClass $record the video mapping record
     * @return string HTML markup
     */
    public static function render(\stdClass $record): string
    {
        $primarysource = get_config('filter_vidrouter', 'primarysource') ?: 'youtube';
        $label = s($record->title ?: $record->urlname);

        switch ($primarysource) {
            case 'youtube':
                if (!empty($record->youtubeid)) {
                    return self::render_youtube_iframe($record->youtubeid, $label);
                }
                break;
        }

        return \html_writer::link('', $label . ' ' . get_string('videourlmissing', 'filter_vidrouter'));
    }

    /**
     * Render a video mapping record into the markup baked into a course backup/export.
     *
     * Used only by backup_local_vidrouter_plugin at backup time. Controlled by the 'embedstyle'
     * setting, independently of what's shown live on the site (see render()): 'iframe' matches
     * the live rendering; 'video' instead emits a plain link, left for filter_mediaplugin/videojs
     * to embed — matching how OLX-exported videos originally rendered, with no captions.
     *
     * @param \stdClass $record the video mapping record
     * @return string HTML markup
     */
    public static function render_for_export(\stdClass $record): string
    {
        $embedstyle = get_config('filter_vidrouter', 'embedstyle') ?: 'iframe';

        if ($embedstyle !== 'video') {
            return self::render($record);
        }

        $primarysource = get_config('filter_vidrouter', 'primarysource') ?: 'youtube';
        $label = s($record->title ?: $record->urlname);

        switch ($primarysource) {
            case 'youtube':
                if (!empty($record->youtubeid)) {
                    return \html_writer::link(
                        'https://www.youtube.com/watch?v=' . $record->youtubeid,
                        $label
                    );
                }
                break;
        }

        return \html_writer::link('', $label . ' ' . get_string('videourlmissing', 'filter_vidrouter'));
    }

    /**
     * Build the native YouTube iframe embed for a video id.
     *
     * @param string $youtubeid
     * @param string $label already-escaped title/label text
     * @return string HTML markup
     */
    private static function render_youtube_iframe(string $youtubeid, string $label): string
    {
        $iframe = \html_writer::tag('iframe', '', [
            'src' => 'https://www.youtube.com/embed/' . $youtubeid,
            'title' => $label,
            'allow' => 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture',
            'allowfullscreen' => 'allowfullscreen',
        ]);
        return \html_writer::div($iframe, 'filter_vidrouter_youtube');
    }

    /**
     * Render the placeholder shown for a shortcode with no matching mapping row.
     *
     * @return string HTML markup
     */
    public static function render_unavailable(): string
    {
        return '<div class="filter_vidrouter_unavailable">' .
               '<p>' . get_string('video_unavailable', 'filter_vidrouter') . '</p>' .
               '</div>';
    }
}
