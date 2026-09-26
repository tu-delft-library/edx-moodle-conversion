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

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/filterlib.php');

/**
 * Resolves a filter_vidrouter_map row into video markup defined in the plugin settings.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class video_renderer
{
    /** Settings that a context may override; anything else stored in filter_config is ignored. */
    public const OVERRIDABLE = ['primarysource', 'fallbacksource', 'embedstyle'];

    /** @var array<int, array> resolved overrides keyed by context id, for the current request only */
    private static array $overridecache = [];

    /**
     * Resolve per-context overrides for a context, inheriting from its parent contexts.
     *
     * Core does not inherit local filter config, so walk the context path from the root down and
     * let the deepest non-empty value win.
     *
     * @param \context $context the context being filtered or exported
     * @return array overridable setting name => value
     */
    public static function overrides_for(\context $context): array
    {
        if (isset(self::$overridecache[$context->id])) {
            return self::$overridecache[$context->id];
        }

        $merged = [];
        foreach (explode('/', trim($context->path, '/')) as $contextid) {
            $local = filter_get_local_config('vidrouter', (int) $contextid);
            foreach (self::OVERRIDABLE as $name) {
                if (isset($local[$name]) && $local[$name] !== '') {
                    $merged[$name] = $local[$name];
                }
            }
        }

        return self::$overridecache[$context->id] = $merged;
    }

    /**
     * Forget resolved overrides, after a save or between tests.
     */
    public static function reset_caches(): void
    {
        self::$overridecache = [];
    }

    /**
     * Render a video mapping record into its live, on-site markup.
     *
     * Used by text_filter on every page view. Always renders the native YouTube iframe (for
     * captions). 
     *
     * @param \stdClass $record the video mapping record
     * @param array $overrides per-context setting overrides (name => value) taking precedence over the site settings
     * @return string HTML markup
     */
    public static function render(\stdClass $record, array $overrides = []): string
    {
        $label = s($record->title ?: $record->urlname);
        $picked = self::pick_source($record, $overrides);

        if ($picked === null) {
            return \html_writer::link('', $label . ' ' . get_string('videourlmissing', 'filter_vidrouter'));
        }

        [$source, $id] = $picked;
        return $source === 'youtube'
            ? self::render_youtube_iframe($id, $label)
            : self::render_collegerama_iframe($id, $label);
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
     * @param array $overrides per-context setting overrides (name => value) taking precedence over the site settings
     * @return string HTML markup
     */
    public static function render_for_export(\stdClass $record, array $overrides = []): string
    {
        $embedstyle = self::setting('embedstyle', 'iframe', $overrides) ?: 'iframe';

        if ($embedstyle !== 'video') {
            return self::render($record, $overrides);
        }

        $label = s($record->title ?: $record->urlname);
        $picked = self::pick_source($record, $overrides);

        if ($picked === null) {
            return \html_writer::link('', $label . ' ' . get_string('videourlmissing', 'filter_vidrouter'));
        }

        [$source, $id] = $picked;
        $url = $source === 'youtube'
            ? 'https://www.youtube.com/watch?v=' . $id
            : 'https://collegerama.tudelft.nl/Mediasite/Play/' . $id;
        return \html_writer::link($url, $label);
    }

    /**
     * Pick which source to render: the primary source if the record has an id for it, otherwise
     * the fallback source (when set and different from the primary).
     *
     * @param \stdClass $record the video mapping record
     * @param array $overrides per-context setting overrides
     * @return array|null [source, id], or null when neither source has an id
     */
    private static function pick_source(\stdClass $record, array $overrides): ?array
    {
        $fields = ['youtube' => 'youtubeid', 'collegeramaid' => 'collegeramaid'];
        $primary = self::setting('primarysource', 'youtube', $overrides);
        $fallback = self::setting('fallbacksource', 'collegeramaid', $overrides);

        foreach ([$primary, $fallback] as $source) {
            if (isset($fields[$source]) && !empty($record->{$fields[$source]})) {
                return [$source, $record->{$fields[$source]}];
            }
        }
        return null;
    }

    /**
     * Resolve a setting: a non-empty per-context override wins, then the site setting, then the default.
     *
     * @param string $name setting name
     * @param string $default value used when the site setting was never saved
     * @param array $overrides per-context overrides (name => value)
     * @return string
     */
    private static function setting(string $name, string $default, array $overrides): string
    {
        if (isset($overrides[$name]) && $overrides[$name] !== '') {
            return $overrides[$name];
        }
        $value = get_config('filter_vidrouter', $name);
        return $value === false ? $default : $value;
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
     * Build the Collegerama (TU Delft Mediasite) iframe embed for a play id. Used as the
     * fallback when the primary source (youtube) has no id — see the 'fallbacksource' setting.
     *
     * @param string $collegeramaid
     * @param string $label already-escaped title/label text
     * @return string HTML markup
     */
    private static function render_collegerama_iframe(string $collegeramaid, string $label): string
    {
        $iframe = \html_writer::tag('iframe', '', [
            'src' => 'https://collegerama.tudelft.nl/Mediasite/Play/' . $collegeramaid,
            'title' => $label,
            'allowfullscreen' => 'allowfullscreen',
        ]);
        return \html_writer::div($iframe, 'filter_vidrouter_collegerama');
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
