import type { DemoRounds, LibraryStats, MatchDetail, MatchSummary } from './api/client'

export const summary: MatchSummary = {
  id: 7, release: 'CS1.5', year: '2002', year_basis: 'HLTV auto-name stamp in demo filename', file_date: '2002-10-03',
  map: 'de_dust2', team1: 'aAa', team2: 'Infinity-eSports', pov: 'HLTV', sides: 'ctt', servers: ['ClanBase HLTV'],
  scores: 'CT 5 : T 7 | CT 2 : T 10', demos: 2, duration_s: 4208, kills: 254,
}

export const stats: LibraryStats = {
  matches: 2092, demos: 4253, rounds: 46476, kills: 279442, player_names: 10716, teams: 869,
  releases: [{ value: 'CS1.5', count: 1500 }, { value: 'CS1.3', count: 300 }],
  maps: [{ value: 'de_dust2', count: 500 }], years: [{ value: '2001', count: 400 }, { value: '2002', count: 900 }, { value: 'unknown-year', count: 30 }],
}

export const detail: MatchDetail = {
  summary,
  release_basis: ['network protocol 46'],
  team_basis: 'player-name clan tag',
  library_name: '[aAa]_[I-eS]_[de_dust2]_[HLTV]_[ctt].rar',
  lineups: [
    { key: 'team1', tag: 'aAa', players: [{ name_id: 1, name: '*aAa* KabaL', steamid: '', aliases: [], kills: 20, deaths: 15, headshots: 4 }] },
    { key: 'team2', tag: 'Infinity-eSports', players: [{ name_id: 2, name: 'Infinity-eSports | Kwak', steamid: 'STEAM_0:1:5', aliases: ['Kwak'], kills: 11, deaths: 24, headshots: 3 }] },
  ],
  demos: [
    {
      sha1: 'a'.repeat(40), part: 1, member: 'aaa-infin-hltv-dust2-round1.dem', label: 'aaa-infin-hltv-dust2-round1.dem',
      recorder_kind: 'hltv', recorder_name: 'HLTV', net_protocol: 46, duration_s: 2047.6, kills: 159, rounds: 2,
      final_score: { CT: 2, TERRORIST: 10 }, engine: 'CS15_P46_hl1110', play_problem: null,
    },
  ],
  sources: [{ file_name: 'x.rar', source_path: '/lib/CS1.5/2002/x.rar', member: 'aaa-infin-hltv-dust2-round1.dem' }],
}

export const rounds: DemoRounds = {
  sha1: 'a'.repeat(40),
  other_kills: 0,
  rounds: [
    { no: 1, start: 0.1, start_basis: 'demo start', end: 13.8, winner: 'TERRORIST', reason: 'Terrorists_Win', score_ct: 0, score_t: 6,
      kills: [{ t: 13.81, killer: '*aAa* KabaL', killer_id: 1, killer_side: 'TERRORIST', victim: 'HellsGate', victim_id: 3, victim_side: 'CT', weapon: 'deagle', headshot: true }] },
    { no: 2, start: 22.8, start_basis: 'RoundTime 300', end: 45.5, winner: 'CT', reason: 'CTs_Win', score_ct: 1, score_t: 6, kills: [] },
  ],
}
