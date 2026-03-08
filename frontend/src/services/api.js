import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Folders API
export const foldersAPI = {
  scan: (path) => api.post('/folders/scan', { path }),
  getStats: (folderId) => api.get(`/folders/stats/${folderId}`),
  list: () => api.get('/folders/list'),
};

// Photos API
export const photosAPI = {
  list: (folderId, params = {}) => 
    api.get(`/photos/list/${folderId}`, { params }),
  get: (photoId) => api.get(`/photos/get/${photoId}`),
  getFile: (photoId, thumb = false) => 
    `${API_BASE_URL}/photos/file/${photoId}?thumb=${thumb}`,
  toggleFavorite: (photoId) => api.post(`/photos/favorite/${photoId}`),
  delete: (photoId) => api.post(`/photos/delete/${photoId}`),
  restore: (photoId) => api.post(`/photos/restore/${photoId}`),
  generateThumbs: (folderId) => api.post(`/photos/generate-thumbs/${folderId}`),
  generateWeb: (folderId, mode = 'web') => 
    api.post(`/photos/generate-web/${folderId}`, null, { params: { mode } }),
  batchOperation: (operation, photoIds) =>
    api.post(`/photos/batch-operation`, { operation, photo_ids: photoIds }),
};

// Similar photos API
export const similarAPI = {
  analyze: (folderId) => api.post(`/similar/analyze/${folderId}`),
  group: (folderId, threshold = 5) => 
    api.post(`/similar/group/${folderId}`, null, { params: { threshold } }),
  getGroups: (folderId, onlyUnreviewed = false) => 
    api.get(`/similar/groups/${folderId}`, { params: { only_unreviewed: onlyUnreviewed } }),
  getGroup: (groupId) => api.get(`/similar/group/${groupId}`),
  selectBest: (groupId, photoId, deleteOthers = false) => 
    api.post(`/similar/group/${groupId}/select/${photoId}`, null, { params: { delete_others: deleteOthers } }),
  skipGroup: (groupId) => api.post(`/similar/group/${groupId}/skip`),
};

// Metadata API
export const metadataAPI = {
  search: (filters) => api.post('/metadata/search', filters),
  getCameras: (folderId) => api.get(`/metadata/cameras/${folderId}`),
  getDateRange: (folderId) => api.get(`/metadata/date-range/${folderId}`),
  getStats: (folderId) => api.get(`/metadata/stats/${folderId}`),
  getByMonth: (folderId) => api.get(`/metadata/by-month/${folderId}`),
  getGPSLocations: (folderId) => api.get(`/metadata/gps-map/${folderId}`),
};

export default api;
