import os, json, UserDict, requests, uuid
from copy import deepcopy
from datetime import datetime
import time

from portality.core import app, current_user

'''
All models in models.py should inherig this DomainObject to know how to save themselves in the index and so on.
You can overwrite and add to the DomainObject functions as required. See models.py for some examples.
'''
    
    
class DomainObject(UserDict.IterableUserDict, object):
    __type__ = None # set the type on the model that inherits this

    def __init__(self, **kwargs):
        if '_source' in kwargs:
            self.data = dict(kwargs['_source'])
            self.meta = dict(kwargs)
            del self.meta['_source']
        else:
            self.data = dict(kwargs)
            
    @classmethod
    def target(cls):
        t = str(app.config['ELASTIC_SEARCH_HOST']).rstrip('/') + '/'
        t += app.config['ELASTIC_SEARCH_DB'] + '/' + cls.__type__ + '/'
        return t
    
    @classmethod
    def makeid(cls):
        '''Create a new id for data object
        overwrite this in specific model types if required'''
        return uuid.uuid4().hex

    @property
    def id(self):
        return self.data.get('id', None)
    
    def set_id(self, id=None):
        if id is None:
            id = self.makeid()
        self.data["id"] = id
    
    @property
    def version(self):
        return self.meta.get('_version', None)

    @property
    def json(self):
        return json.dumps(self.data)
    
    def set_created(self, date=None):
        if date is None:
            self.data['created_date'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            self.data['created_date'] = date

    @property
    def created_date(self):
        return self.data.get("created_date")
    
    @property
    def last_updated(self):
        return self.data.get("last_updated")

    def save(self):
        if 'id' in self.data:
            id_ = self.data['id'].strip()
        else:
            id_ = self.makeid()
            self.data['id'] = id_
        
        self.data['last_updated'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        if 'created_date' not in self.data:
            self.data['created_date'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        """
        if 'author' not in self.data:
            try:
                self.data['author'] = current_user.id
            except:
                self.data['author'] = "anonymous"
        """
        
        r = requests.post(self.target() + self.data['id'], data=json.dumps(self.data))
        
        if r.status_code >= 400:
            print r.json()

    def save_from_form(self,request):
        newdata = request.json if request.json else request.values
        for k, v in newdata.items():
            if k not in ['submit']:
                self.data[k] = v
        self.save()

    @classmethod
    def bulk(cls, bibjson_list, idkey='id', refresh=False):
        data = ''
        for r in bibjson_list:
            data += json.dumps( {'index':{'_id':r[idkey]}} ) + '\n'
            data += json.dumps( r ) + '\n'
        r = requests.post(cls.target() + '_bulk', data=data)
        if refresh:
            cls.refresh()
        return r.json()


    @classmethod
    def refresh(cls):
        r = requests.post(cls.target() + '_refresh')
        return r.json()


    @classmethod
    def pull(cls, id_):
        '''Retrieve object by id.'''
        if id_ is None:
            return None
        try:
            out = requests.get(cls.target() + id_)
            if out.status_code == 404:
                return None
            else:
                return cls(**out.json())
        except:
            return None

    @classmethod
    def pull_by_key(cls,key,value):
        res = cls.query(q={"query":{"term":{key+app.config['FACET_FIELD']:value}}})
        if res.get('hits',{}).get('total',0) == 1:
            return cls.pull( res['hits']['hits'][0]['_source']['id'] )
        else:
            return None


    @classmethod
    def keys(cls,mapping=False,prefix=''):
        # return a sorted list of all the keys in the index
        if not mapping:
            mapping = cls.query(endpoint='_mapping')[cls.__type__]['properties']
        keys = []
        for item in mapping:
            if mapping[item].has_key('fields'):
                for item in mapping[item]['fields'].keys():
                    if item != 'exact' and not item.startswith('_'):
                        keys.append(prefix + item + app.config['FACET_FIELD'])
            else:
                keys = keys + cls.keys(mapping=mapping[item]['properties'],prefix=prefix+item+'.')
        keys.sort()
        return keys
        
    @staticmethod
    def make_query(recid='', endpoint='_search', q='', terms=None, facets=None, **kwargs):
        '''
        Generate a query object based on parameters but don't sent to
        backend - return it instead. Must always have the same
        parameters as the query method. See query method for explanation
        of parameters.
        '''
        if recid and not recid.endswith('/'): recid += '/'
        if isinstance(q,dict):
            query = q
            if 'bool' not in query['query']:
                boolean = {'bool':{'must': [] }}
                boolean['bool']['must'].append( query['query'] )
                query['query'] = boolean
            if 'must' not in query['query']['bool']:
                query['query']['bool']['must'] = []
        elif q:
            query = {
                'query': {
                    'bool': {
                        'must': [
                            {'query_string': { 'query': q }}
                        ]
                    }
                }
            }
        else:
            query = {
                'query': {
                    'bool': {
                        'must': [
                            {'match_all': {}}
                        ]
                    }
                }
            }

        if facets:
            if 'facets' not in query:
                query['facets'] = {}
            for k, v in facets.items():
                query['facets'][k] = {"terms":v}

        if terms:
            boolean = {'must': [] }
            for term in terms:
                if not isinstance(terms[term],list): terms[term] = [terms[term]]
                for val in terms[term]:
                    obj = {'term': {}}
                    obj['term'][ term ] = val
                    boolean['must'].append(obj)
            if q and not isinstance(q,dict):
                boolean['must'].append( {'query_string': { 'query': q } } )
            elif q and 'query' in q:
                boolean['must'].append( query['query'] )
            query['query'] = {'bool': boolean}

        for k,v in kwargs.items():
            if k == '_from':
                query['from'] = v
            else:
                query[k] = v
        
        return query

    @classmethod
    def query(cls, recid='', endpoint='_search', q='', terms=None, facets=None, **kwargs):
        '''Perform a query on backend.

        :param recid: needed if endpoint is about a record, e.g. mlt
        :param endpoint: default is _search, but could be _mapping, _mlt, _flt etc.
        :param q: maps to query_string parameter if string, or query dict if dict.
        :param terms: dictionary of terms to filter on. values should be lists. 
        :param facets: dict of facets to return from the query.
        :param kwargs: any keyword args as per
            http://www.elasticsearch.org/guide/reference/api/search/uri-request.html
        '''
        query = cls.make_query(recid, endpoint, q, terms, facets, **kwargs)
        return cls.send_query(query, endpoint=endpoint, recid=recid)


    @classmethod
    def send_query(cls, qobj, endpoint='_search', recid='', retry=50):
        '''Actually send a query object to the backend.'''
        r = None
        count = 0
        exception = None
        while count < retry:
            count += 1
            try:
                if endpoint in ['_mapping']:
                    r = requests.get(cls.target() + recid + endpoint)
                else:
                    r = requests.post(cls.target() + recid + endpoint, data=json.dumps(qobj))
                break
            except Exception as e:
                exception = e
            time.sleep(0.5)
                
        if r is not None:
            return r.json()
        if exception is not None:
            raise exception
        raise Exception("Couldn't get the ES query endpoint to respond.  Also, you shouldn't be seeing this.")

    def accessed(self):
        if 'last_access' not in self.data:
            self.data['last_access'] = []
        try:
            usr = current_user.id
        except:
            usr = "anonymous"
        self.data['last_access'].insert(0, { 'user':usr, 'date':datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ") } )
        r = requests.put(self.target() + self.data['id'], data=json.dumps(self.data))

    def delete(self):        
        r = requests.delete(self.target() + self.id)
    
    @classmethod
    def remove_by_id(self, id):
        r = requests.delete(self.target() + id)
    
    def update(self, doc):
        """
        add the provided doc to the existing object
        """
        return requests.post(self.target() + self.id + "/_update", data=json.dumps({"doc" : doc}))
    
    @classmethod
    def delete_all(cls):
        r = requests.delete(cls.target())
        r = requests.put(cls.target() + '_mapping', json.dumps(app.config['MAPPINGS'][cls.__type__]))
    
    @classmethod
    def iterate(cls, q, page_size=1000, limit=None, wrap=True):
        q["size"] = page_size
        q["from"] = 0
        if "sort" not in q: # to ensure complete coverage on a changing index, sort by id is our best bet
            q["sort"] = [{"id" : {"order" : "asc"}}]
        counter = 0
        while True:
            # apply the limit
            if limit is not None and counter >= limit:
                break
            
            res = cls.query(q=q)
            rs = [r.get("_source") if "_source" in r else r.get("fields") for r in res.get("hits", {}).get("hits", [])]
            # print counter, len(rs), res.get("hits", {}).get("total"), len(res.get("hits", {}).get("hits", [])), json.dumps(q)
            if len(rs) == 0:
                break
            for r in rs:
                # apply the limit (again)
                if limit is not None and counter >= limit:
                    break
                counter += 1
                if wrap:
                    yield cls(**r)
                else:
                    yield r
            q["from"] += page_size   
    
    @classmethod
    def iterall(cls, page_size=1000, limit=None):
        return cls.iterate(deepcopy(all_query), page_size, limit)
    
    def csv(self, multival_sep=','):
        raise NotImplementedError

    @classmethod
    def prefix_query(cls, field, prefix, size=5):
        # example of a prefix query
        # {
        #     "query": {"prefix" : { "bibjson.publisher" : "ope" } },
        #     "size": 0,
        #     "facets" : {
        #       "publisher" : { "terms" : {"field" : "bibjson.publisher.exact", "size": 5} }
        #     }
        # }
        if field.endswith(app.config['FACET_FIELD']):
            # strip .exact (or whatever it's configured as) off the end
            query_field = field[:field.rfind(app.config['FACET_FIELD'])]
        else:
            query_field = field

        # the actual terms should come from the .exact version of the
        # field - we are suggesting whole values, not fragments
        facet_field = query_field + app.config['FACET_FIELD']

        q = {
            "query": {"prefix" : { query_field : prefix } },
            "size": 0,
            "facets" : {
              field : { "terms" : {"field" : facet_field, "size": size} }
            }
        }

        return cls.send_query(q)

    @classmethod
    def autocomplete(cls, field, prefix, size=5):
        res = cls.prefix_query(field, prefix, size=size)
        result = []
        for term in res['facets'][field]['terms']:
            # keep ordering - it's by count by default, so most frequent
            # terms will now go to the front of the result list
            result.append({"id": term['term'], "text": term['term']})
        return result
        

########################################################################
## Some useful ES queries
########################################################################

all_query = { 
    "query" : { 
        "match_all" : { }
    }
}
